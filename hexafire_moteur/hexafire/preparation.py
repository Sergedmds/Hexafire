# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
"""Étape 2 : préparation des détections (règles P1 à P9 du document de conception).

Pour chaque archive mensuelle :
  - lecture et mise au schéma commun ;
  - filtres : type « feu de végétation » (P4), confiance MODIS >= 30 (P3),
    classe VIIRS « faible » exclue (P2), coordonnées valides ;
  - rattachement à la cellule de 0,25° (P7) ;
  - écriture d'un fichier par capteur et par mois dans donnees_preparees/ ;
  - journal : empreinte SHA-256 de la source, effectifs avant/après chaque filtre (D1, D2).

Une archive déjà préparée (même empreinte) est sautée : on peut relancer
la préparation à tout moment pendant que les téléchargements continuent.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from . import grille, tables
from .config import Config
from .lecture import Archive, inventaire, lire_archive

COLONNES_SORTIE = ["cellule", "capteur", "annee", "mois", "date", "hhmm", "jour_nuit",
                   "lat", "lon", "frp", "conf", "type", "sample", "vza", "pixarea"]


def sha256(chemin: Path, bloc: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        while chunk := f.read(bloc):
            h.update(chunk)
    return h.hexdigest()


def chemin_sortie(cfg: Config, capteur: str, annee: int, mois: int) -> Path:
    return tables.chemin_table(cfg.donnees_preparees / capteur / f"{annee}",
                               f"{capteur}_{annee}{mois:02d}")


def filtrer(df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, dict]:
    eff = {"lues": int(len(df))}

    ok = df["lat"].between(-90, 90) & df["lon"].between(-180, 180) & df["capteur"].notna()
    eff["coord_invalides"] = int((~ok).sum())

    t = df["type"].isin(cfg.types_conserves)
    eff["type_exclu"] = int((ok & ~t).sum())
    ok &= t

    modis = df["famille"].eq("MODIS")
    conf_modis = pd.to_numeric(df["conf"], errors="coerce")
    c_modis = ~modis | (conf_modis >= cfg.confiance_modis_min)
    c_viirs = modis | ~df["conf"].isin(cfg.confiance_viirs_exclues)
    c = c_modis & c_viirs
    eff["confiance_exclue"] = int((ok & ~c).sum())
    ok &= c

    jn = df["jour_nuit"].isin(["J", "N"])
    eff["jour_nuit_inconnu"] = int((ok & ~jn).sum())
    ok &= jn

    eff["retenues"] = int(ok.sum())
    # Contrôle de conservation : chaque ligne lue est soit retenue soit comptée dans un motif d'exclusion
    assert eff["lues"] == eff["retenues"] + eff["coord_invalides"] + eff["type_exclu"] \
        + eff["confiance_exclue"] + eff["jour_nuit_inconnu"], "conservation des effectifs violée"
    return df.loc[ok].copy(), eff


def _journal_existant(cfg: Config) -> dict[str, dict]:
    j = cfg.journaux / "preparation.jsonl"
    vus = {}
    if j.exists():
        for ligne in j.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                r = json.loads(ligne)
                vus[r["fichier"]] = r
    return vus


def preparer_archive(a: Archive, cfg: Config, vus: dict | None = None, forcer: bool = False) -> dict | None:
    empreinte = sha256(a.chemin)
    deja = (vus or {}).get(a.chemin.name)
    if deja and not forcer and deja.get("sha256") == empreinte and all(
            Path(p).exists() for p in deja.get("sorties", [])):
        return None  # déjà fait

    t0 = time.time()
    brut = lire_archive(a)
    det, eff = filtrer(brut, cfg)
    det["cellule"] = grille.cellule(det["lat"].to_numpy(), det["lon"].to_numpy(), cfg.pas)

    sorties, par_capteur = [], {}
    # Une archive mensuelle peut contenir quelques détections du mois voisin : elles restent
    # dans le fichier de l'archive, mais leurs colonnes annee/mois donnent leur vrai mois,
    # et c'est ce mois-là qui est utilisé par l'agrégation.
    eff["hors_mois"] = int(((det["annee"] != a.annee) | (det["mois"] != a.mois)).sum())
    for capteur, sous in det.groupby("capteur", sort=True):
        dest = chemin_sortie(cfg, capteur, a.annee, a.mois)
        tables.ecrire(sous[COLONNES_SORTIE].sort_values(["date", "hhmm"]), dest)
        sorties.append(str(dest))
        par_capteur[capteur] = int(len(sous))

    rec = {
        "fichier": a.chemin.name, "produit": a.produit, "annee": a.annee, "mois": a.mois,
        "collection": a.collection, "version": a.version, "sha256": empreinte,
        "effectifs": eff, "par_capteur": par_capteur, "sorties": sorted(set(sorties)),
        "duree_s": round(time.time() - t0, 1), "date_traitement": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    cfg.journaux.mkdir(parents=True, exist_ok=True)
    with open(cfg.journaux / "preparation.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def preparer_tout(cfg: Config, produits: list[str] | None = None, limite: int | None = None,
                  forcer: bool = False) -> list[dict]:
    archives = inventaire(cfg.donnees_brutes)
    if produits:
        archives = [a for a in archives if a.produit in produits]
    vus = _journal_existant(cfg)
    faits = []
    for i, a in enumerate(archives):
        if limite is not None and len(faits) >= limite:
            break
        try:
            r = preparer_archive(a, cfg, vus, forcer)
        except (EOFError, OSError, pd.errors.ParserError) as e:
            # typiquement : archive en cours de téléchargement, encore incomplète
            print(f"[{i + 1}/{len(archives)}] {a.chemin.name} : ignorée ({type(e).__name__}: {e})")
            continue
        if r is None:
            continue
        e = r["effectifs"]
        print(f"[{i + 1}/{len(archives)}] {a.chemin.name} : {e['lues']:>9,} lues, "
              f"{e['retenues']:>9,} retenues ({r['duree_s']} s)")
        faits.append(r)
    return faits
