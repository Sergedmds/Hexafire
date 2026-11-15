# Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
"""Mois récents : récupération via l'API FIRMS pour la période non couverte par les archives mensuelles.

Les archives de l'Université du Maryland sont publiées 1 à 2 mois après la fin du mois. Pour les mois
suivants, on interroge l'API FIRMS (zone « world », 5 jours maximum par requête, 5 000 transactions
par tranche de 10 minutes), en préférant le produit standard (SP) quand il existe, sinon le temps
quasi réel (NRT).

    export FIRMS_MAP_KEY=votre_cle          # ou --cle
    python -m hexafire firms                # télécharge puis prépare les mois récents
    python -m hexafire agreger              # les fichiers « _api » sont pris en compte

Les réponses brutes vont dans donnees_brutes/firms_api/<SOURCE>/<date>.csv (on reprend où on s'était
arrêté). Les détections préparées vont dans donnees_preparees/<capteur>/<année>/<capteur>_<AAAAMM>_api.*.
Quand le mois correspondant de l'archive mensuelle arrive, c'est l'archive qui est utilisée (agreger
ignore alors le fichier « _api »).

Le temps quasi réel ne contient pas toujours la colonne « type » (source fixe, volcan) : on masque
alors les détections situées sur des sources fixes connues, repérées dans les archives MODIS récentes.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import grille, tables
from .config import Config
from .lecture import inventaire
from .preparation import COLONNES_SORTIE

URL = "https://firms.modaps.eosdis.nasa.gov/api"
SOURCES = {  # capteur(s) -> préfixe de source FIRMS
    "MODIS": "MODIS", "S-NPP": "VIIRS_SNPP", "NOAA-20": "VIIRS_NOAA20", "NOAA-21": "VIIRS_NOAA21",
}
PRODUIT_ARCHIVE = {"MODIS": "MCD14ML", "S-NPP": "VNP14IMGML", "NOAA-20": "VJ114IMGML", "NOAA-21": "VJ214IMGML"}
FIN_SNPP = dt.date(2026, 11, 2)
PAS_MASQUE = 0.05


def _get(url: str, essais: int = 4) -> str:
    import requests
    for k in range(essais):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 503):
                time.sleep(60 * (k + 1))
                continue
            raise RuntimeError(f"HTTP {r.status_code} : {r.text[:200]}")
        except requests.RequestException as e:
            if k == essais - 1:
                raise
            time.sleep(20 * (k + 1))
    raise RuntimeError("échec répété")


def disponibilite(cle: str) -> dict[str, tuple[dt.date, dt.date]]:
    txt = _get(f"{URL}/data_availability/csv/{cle}/all")
    df = pd.read_csv(io.StringIO(txt))
    return {r.data_id: (pd.to_datetime(r.min_date).date(), pd.to_datetime(r.max_date).date())
            for r in df.itertuples()}


# Dernier mois publié sur le serveur d'archives (constaté le 12/11/2026 avec telecharger_archives.sh versions).
# L'API ne sert qu'APRÈS ces dates : les mois antérieurs viennent des archives, même si leur téléchargement
# n'est pas encore terminé sur ce PC. Mettre à jour quand de nouveaux mois sont publiés.
FIN_ARCHIVE_SERVEUR = {"MODIS": (2026, 8), "S-NPP": (2026, 7), "NOAA-20": (2026, 7), "NOAA-21": (2026, 7)}


def premier_jour_apres_archive(cfg: Config) -> dict[str, dt.date]:
    arch = inventaire(cfg.donnees_brutes)
    debut = {}
    for famille, prod in PRODUIT_ARCHIVE.items():
        fin = FIN_ARCHIVE_SERVEUR[famille]
        local = sorted((a.annee, a.mois) for a in arch if a.produit == prod)
        if local and local[-1] > fin:   # le serveur a publié de nouveaux mois depuis
            fin = local[-1]
        a, m = fin
        debut[famille] = dt.date(a + (m == 12), m % 12 + 1, 1)
    return debut


def telecharger(cfg: Config, cle: str, fin: dt.date | None = None, capteurs: list[str] | None = None) -> list[Path]:
    try:
        dispo = disponibilite(cle)
    except Exception as e:  # la disponibilité n'est qu'une optimisation : on passe en NRT si elle échoue
        print(f"  disponibilité des produits non lue ({e}) : utilisation du temps quasi réel (NRT)")
        dispo = {}
    fin = fin or dt.date.today()
    fichiers = []
    for famille, debut in premier_jour_apres_archive(cfg).items():
        if capteurs and famille not in capteurs:
            continue
        prefixe = SOURCES[famille]
        fin_f = min(fin, FIN_SNPP) if famille == "S-NPP" else fin
        jour = debut
        while jour <= fin_f:
            n = min(5, (fin_f - jour).days + 1)
            dernier = jour + dt.timedelta(days=n - 1)
            sp = dispo.get(f"{prefixe}_SP")
            source = f"{prefixe}_SP" if sp and dernier <= sp[1] else f"{prefixe}_NRT"
            dest = cfg.donnees_brutes / "firms_api" / source / f"{jour.isoformat()}_{n}j.csv"
            if not dest.exists():
                txt = _get(f"{URL}/area/csv/{cle}/{source}/world/{n}/{jour.isoformat()}")
                if not txt.startswith("latitude"):
                    print(f"  {source} {jour} : réponse inattendue -> {txt[:120]!r}")
                    jour = dernier + dt.timedelta(days=1)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(".tmp")
                tmp.write_text(txt)
                tmp.replace(dest)
                print(f"  {source} {jour} +{n} j : {txt.count(chr(10)) - 1:,} détections")
                time.sleep(1.0)
            fichiers.append(dest)
            jour = dernier + dt.timedelta(days=1)
    return fichiers


def masque_sources_fixes(cfg: Config, annees_min: int = 2022) -> set[int]:
    """Clés (grille de 0,05°) des détections de type 1 ou 2 dans les archives MODIS récentes."""
    chemin = cfg.agregats / "sources_fixes.csv"
    if chemin.exists():
        return set(pd.read_csv(chemin)["cle"].astype("int64"))
    cles: set[int] = set()
    for a in inventaire(cfg.donnees_brutes):
        if a.produit == "MCD14ML" and a.annee >= annees_min:
            df = pd.read_csv(a.chemin, sep=r"\s+", usecols=["lat", "lon", "type"])
            df = df[df["type"].isin([1, 2])]
            cles.update(grille.cellule(df["lat"].to_numpy(), df["lon"].to_numpy(), PAS_MASQUE).tolist())
    cfg.agregats.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"cle": sorted(cles)}).to_csv(chemin, index=False)
    return cles


def _capteur(source: str, sat: pd.Series) -> pd.Series:
    if source.startswith("MODIS"):
        s = sat.astype(str).str.strip().str.upper().str[0]
        return s.map({"T": "Terra", "A": "Aqua"})
    return pd.Series({"VIIRS_SNPP": "S-NPP", "VIIRS_NOAA20": "NOAA-20", "VIIRS_NOAA21": "NOAA-21"}[
        source.rsplit("_", 1)[0]], index=sat.index)


def preparer_api(cfg: Config) -> int:
    racine = cfg.donnees_brutes / "firms_api"
    if not racine.exists():
        print("Aucun fichier API : lancez d'abord le téléchargement.")
        return 0
    masque = masque_sources_fixes(cfg)
    morceaux = []
    for f in sorted(racine.rglob("*.csv")):
        source = f.parent.name
        df = pd.read_csv(f, dtype={"acq_time": "int64", "confidence": "string", "daynight": "string"})
        if df.empty:
            continue
        cap = _capteur(source, df["satellite"] if "satellite" in df else pd.Series("", index=df.index))
        out = pd.DataFrame({
            "capteur": cap,
            "date": pd.to_datetime(df["acq_date"]).dt.strftime("%Y%m%d").astype("int64"),
            "hhmm": df["acq_time"].astype("int64"),          # 236 = 02 h 36 (règle P1)
            "lat": df["latitude"].astype("float64"), "lon": df["longitude"].astype("float64"),
            "frp": df["frp"].astype("float64"),
            "conf": df["confidence"].str.strip().str.lower(),
            "jour_nuit": df["daynight"].str.strip().str.upper().map({"D": "J", "N": "N"}),
            "type": df["type"].astype("int64") if "type" in df else -1,
            "sample": np.nan, "vza": np.nan, "pixarea": np.nan,
            "famille": "MODIS" if source.startswith("MODIS") else "VIIRS",
        })
        morceaux.append(out)
    if not morceaux:
        return 0
    d = pd.concat(morceaux, ignore_index=True).drop_duplicates(["capteur", "date", "hhmm", "lat", "lon"])
    lues = len(d)
    ok = d["capteur"].notna() & d["jour_nuit"].isin(["J", "N"])
    ok &= np.where(d["type"] >= 0, d["type"].isin(cfg.types_conserves), True)
    sans_type = d["type"] < 0
    fixe = np.isin(grille.cellule(d["lat"].to_numpy(), d["lon"].to_numpy(), PAS_MASQUE), list(masque))
    ok &= ~(sans_type & fixe)
    conf_num = pd.to_numeric(d["conf"], errors="coerce")
    ok &= np.where(d["famille"] == "MODIS", conf_num >= cfg.confiance_modis_min,
                   ~d["conf"].isin(cfg.confiance_viirs_exclues))
    d = d[ok].copy()
    d["annee"], d["mois"] = d["date"] // 10000, d["date"] // 100 % 100
    d["cellule"] = grille.cellule(d["lat"].to_numpy(), d["lon"].to_numpy(), cfg.pas)
    n = 0
    for (cap, an, mo), g in d.groupby(["capteur", "annee", "mois"]):
        dest = tables.chemin_table(cfg.donnees_preparees / cap / f"{an}", f"{cap}_{an}{mo:02d}_api")
        tables.ecrire(g[COLONNES_SORTIE].sort_values(["date", "hhmm"]), dest)
        n += 1
    print(f"API FIRMS : {lues:,} détections lues, {len(d):,} retenues, {n} fichiers capteur-mois écrits")
    return n


def executer(cfg: Config, cle: str | None, capteurs: list[str] | None = None) -> None:
    cle = cle or os.environ.get("FIRMS_MAP_KEY")
    if not cle:
        raise SystemExit("Clé FIRMS manquante : export FIRMS_MAP_KEY=... ou --cle ...")
    debuts = premier_jour_apres_archive(cfg)
    for f, d in debuts.items():
        print(f"  {f} : archive jusqu'au {d - dt.timedelta(days=1)}, API à partir du {d}")
    telecharger(cfg, cle, capteurs=capteurs)
    preparer_api(cfg)
