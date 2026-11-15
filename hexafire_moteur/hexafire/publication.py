# Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
"""Étape 6 : publication des fichiers lus par l'application web (format d'échange v1).

Dossier produit (par défaut ../hexafire_web/donnees) :

    index.json                 métadonnées, liste des mois avec statut, liste des tuiles, validation
    tuiles/t_<ilat>_<ilon>.json une tuile de 5° x 5° :
        {"cellules": [...],         identifiants de cellules de 0,25° (voir grille.py)
         "t": [...],                indice du mois : 0 = novembre 2000, 1 = décembre 2000, ...
         "v": [...],                points chauds harmonisés (équivalent MODIS, jour + nuit)
         "b": [...],                détections brutes de la source utilisée ce mois-là (MODIS ou VIIRS)
         "w": [...],                même grandeur en équivalent VIIRS S-NPP (ce que S-NPP seul aurait détecté)
         "e": [...], "f": [...],    écart type dû à la conversion, en équivalent MODIS (e) et VIIRS (f)
         "p": [...]}                FRP totale (MW) des détections brutes b ; FRP moyenne = p / b (non harmonisée)
    Les listes ont la même longueur ; seules les valeurs non nulles sont écrites.
    cartes/m_<t>.json           couche de la carte pour le mois t, sur une grille de 1° :
        {"c": [...], "v": [...], "w": [...], "r": [...]}
        r = rapport à la médiane 2003-2020 du même mois pour la cellule de 1°, -1 si non calculable
        (moins de 10 années de référence ou médiane < 5). Cellules écrites : v > 0 ou médiane >= 5.
    Un mois « mesuré », « converti » ou « provisoire » sans valeur pour une cellule vaut 0.

`python -m hexafire publier --exemple` écrit un jeu fictif au même format, pour développer
l'interface avant que la série réelle soit complète.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import grille, occasions, tables
from .config import Config

DEBUT = (2000, 11)
TAILLE_TUILE = 5.0
PAS_CARTE = 1.0
VERSION_FORMAT = 2
OBSERVES = ("mesuré", "converti", "provisoire")
UNITES = {"modis": "points chauds, équivalent MODIS Terra + Aqua (jour + nuit)",
          "viirs": "points chauds, équivalent VIIRS S-NPP (jour + nuit)"}


def indice_mois(annee, mois):
    return (np.asarray(annee) - DEBUT[0]) * 12 + (np.asarray(mois) - DEBUT[1])


def id_tuile(lat, lon) -> np.ndarray:
    ilat = np.floor((np.asarray(lat) + 90) / TAILLE_TUILE).astype(int)
    ilon = np.floor((np.asarray(lon) + 180) / TAILLE_TUILE).astype(int)
    return np.char.add(np.char.add(ilat.astype(str), "_"), ilon.astype(str))


def _ecrire_tuiles(df: pd.DataFrame, dossier: Path, pas: float) -> list[str]:
    """df : cellule, t, v."""
    lat, lon = grille.centre(df["cellule"].to_numpy(), pas)
    df = df.assign(tuile=id_tuile(lat, lon))
    (dossier / "tuiles").mkdir(parents=True, exist_ok=True)
    for f in (dossier / "tuiles").glob("t_*.json"):
        f.unlink()
    ids = []
    for tid, g in df.groupby("tuile", sort=True):
        g = g.sort_values(["cellule", "t"])
        contenu = {"cellules": g["cellule"].astype(int).tolist(), "t": g["t"].astype(int).tolist(),
                   "v": [round(float(x), 2) for x in g["v"]]}
        if "b" in g:   # détections brutes de la source utilisée ce mois-là (pour la preuve « brut / harmonisé »)
            contenu["b"] = g["b"].astype(int).tolist()
        if "w" in g:   # équivalent VIIRS S-NPP
            contenu["w"] = [round(float(x), 2) for x in g["w"]]
        if "p" in g:   # FRP totale (MW) des détections brutes de la source du mois (non harmonisée)
            contenu["p"] = [round(float(x), 1) for x in g["p"]]
        if "e" in g:   # écarts types de conversion (équivalent MODIS, équivalent VIIRS)
            contenu["e"] = [round(float(x), 2) for x in g["e"]]
            contenu["f"] = [round(float(x), 2) for x in g["f"]]
        (dossier / "tuiles" / f"t_{tid}.json").write_text(json.dumps(contenu, separators=(",", ":")))
        ids.append(str(tid))
    return ids


def _ecrire_cartes(df: pd.DataFrame, mois: pd.DataFrame, dossier: Path, pas: float,
                   reference: tuple[int, int] = (2003, 2020)) -> int:
    """Couche mensuelle de la carte sur une grille de PAS_CARTE degrés.

    df : cellule, t, v (et w) ; mois : t, annee, mois, statut.
    La normale d'une cellule de 1° est la médiane du même mois de l'année sur la période de
    référence (mois observés seulement, 0 si aucun point chaud). Mêmes règles de refus que
    l'application : au moins 10 années de référence et une médiane d'au moins 5.
    """
    lat, lon = grille.centre(df["cellule"].to_numpy(), pas)
    c1 = grille.cellule(lat, lon, PAS_CARTE)
    a = df.assign(c=c1).groupby(["c", "t"])[[x for x in ("v", "w") if x in df]].sum().reset_index()
    cellules, ic = np.unique(a["c"].to_numpy(), return_inverse=True)
    nt = int(mois["t"].max()) + 1
    V = np.zeros((len(cellules), nt), dtype="float32")
    V[ic, a["t"].to_numpy()] = a["v"].to_numpy()
    W = None
    if "w" in a:
        W = np.zeros_like(V)
        W[ic, a["t"].to_numpy()] = a["w"].to_numpy()
    m = mois.set_index("t")
    obs = m["statut"].isin(OBSERVES)
    med = np.zeros((len(cellules), 12), dtype="float32")
    n_ref = np.zeros(12, dtype=int)
    for k in range(1, 13):
        cols = m.index[obs & (m["mois"] == k) & m["annee"].between(*reference)].to_numpy()
        n_ref[k - 1] = len(cols)
        if len(cols):
            med[:, k - 1] = np.median(V[:, cols], axis=1)
    (dossier / "cartes").mkdir(parents=True, exist_ok=True)
    for f in (dossier / "cartes").glob("m_*.json"):
        f.unlink()
    n = 0
    for t, r in m.iterrows():
        if r["statut"] == "non observé":
            continue
        k = int(r["mois"]) - 1
        v, md = V[:, t], med[:, k]
        garder = (v > 0) | (md >= 5)
        ok = (md >= 5) & (n_ref[k] >= 10)
        rap = np.where(ok, v / np.where(md > 0, md, 1), -1.0)
        contenu = {"c": cellules[garder].astype(int).tolist(),
                   "v": [round(float(x), 1) for x in v[garder]],
                   "r": [round(float(x), 2) for x in rap[garder]]}
        if W is not None:
            contenu["w"] = [round(float(x), 1) for x in W[garder, t]]
        (dossier / "cartes" / f"m_{int(t)}.json").write_text(json.dumps(contenu, separators=(",", ":")))
        n += 1
    return n


def equivalent_viirs(cfg: Config, s: pd.DataFrame, taille_bloc: float = 10.0) -> pd.Series | None:
    """N_harm (équivalent MODIS Terra + Aqua) -> ce que VIIRS S-NPP seul aurait détecté.

    w = N_harm * exp(alpha_S-NPP(strate, mois, période)) * E_S-NPP / (E_Terra + E_Aqua),
    l'inverse exact de la conversion utilisée pour la série (même alpha, mêmes occasions).
    s : cellule, mois, jour_nuit, N_harm. Renvoie None si la conversion S-NPP n'existe pas.
    """
    from .harmonisation import strate_bloc
    ch = tables.chemin_table(cfg.agregats, "conversion_snpp")
    if not ch.exists():
        return None
    conv = tables.lire(ch)[["strate", "mois", "jour_nuit", "alpha_stab"]]
    x = s[["cellule", "mois", "jour_nuit", "N_harm"]].copy()
    x["strate"] = strate_bloc(x["cellule"].to_numpy(), cfg.pas, taille_bloc)
    x = x.merge(conv, on=["strate", "mois", "jour_nuit"], how="left")
    repli = conv.groupby("jour_nuit")["alpha_stab"].median()
    a = x["alpha_stab"].fillna(x["jour_nuit"].map(repli)).fillna(conv["alpha_stab"].median()).to_numpy()
    lat, _ = grille.centre(x["cellule"].to_numpy(), cfg.pas)
    rapport_e = occasions.passages_par_jour(lat, "S-NPP") / (
        occasions.passages_par_jour(lat, "Terra") + occasions.passages_par_jour(lat, "Aqua"))
    return pd.Series(x["N_harm"].to_numpy() * np.exp(a) * rapport_e, index=s.index)


def incertitude(cfg: Config, s: pd.DataFrame, taille_bloc: float = 10.0) -> tuple[pd.Series, pd.Series] | None:
    """Écart type absolu dû à la conversion, pour chaque ligne (cellule, mois, période) de la série.

    Sur l'échelle log, l'erreur type d'une valeur convertie est celle du facteur appliqué :
      - mois MODIS mesurés ou provisoires : aucune en équivalent MODIS ; se(alpha_S-NPP) en équivalent VIIRS ;
      - Terra seul (2000-2002) : se(gamma) en équivalent MODIS ; racine(se(gamma)^2 + se(alpha)^2) en VIIRS ;
      - VIIRS converti : se(alpha) en équivalent MODIS ; aucune en équivalent VIIRS (approximation :
        S-NPP dominant ; l'écart du relais NOAA est inclus dans se(alpha) des tables NOAA).
    Écart type absolu = valeur x erreur type (approximation au premier ordre).
    Renvoie (sd_modis, sd_viirs) alignés sur s, ou None si la conversion S-NPP n'existe pas.
    """
    from .harmonisation import se_gamma, se_stabilise, strate_bloc
    ch = tables.chemin_table(cfg.agregats, "conversion_snpp")
    if not ch.exists():
        return None
    conv = tables.lire(ch)
    if "se_stab" not in conv:
        conv["se_stab"] = se_stabilise(conv)
    x = s[["cellule", "mois", "jour_nuit", "N_harm", "source"]].copy()
    x["strate"] = strate_bloc(x["cellule"].to_numpy(), cfg.pas, taille_bloc)
    x = x.merge(conv[["strate", "mois", "jour_nuit", "se_stab"]], on=["strate", "mois", "jour_nuit"], how="left")
    repli = np.nanmedian(conv["se_stab"].to_numpy(dtype="float64"))
    se_a = x["se_stab"].fillna(repli).to_numpy(dtype="float64")
    se_g = np.zeros(len(x))
    cht = tables.chemin_table(cfg.agregats, "conversion_terra")
    if cht.exists():
        g = tables.lire(cht)
        if "se_gamma" not in g:
            g["se_gamma"] = se_gamma(g["nT"], g["nM"])
        x = x.merge(g[["strate", "mois", "jour_nuit", "se_gamma"]], on=["strate", "mois", "jour_nuit"], how="left")
        se_g = x["se_gamma"].fillna(0.0).to_numpy(dtype="float64")
    src = x["source"].astype(str)
    terra = src.str.startswith("Terra").to_numpy()
    viirs = src.str.startswith("VIIRS").to_numpy()
    rel_m = np.where(terra, se_g, np.where(viirs, se_a, 0.0))
    rel_v = np.where(terra, np.sqrt(se_g ** 2 + se_a ** 2), np.where(viirs, 0.0, se_a))
    n = x["N_harm"].to_numpy(dtype="float64")
    return (pd.Series(n * rel_m, index=s.index), pd.Series(n * rel_v, index=s.index))


def frp_source(cfg: Config, s: pd.DataFrame, source: pd.Series) -> np.ndarray:
    """FRP totale des détections brutes du capteur utilisé ce mois-là, pour chaque ligne (cellule, annee, mois) de s.

    Terra seul -> Terra ; MODIS -> Terra + Aqua ; VIIRS -> plateformes VIIRS. La FRP n'est pas harmonisée :
    pour un même feu, MODIS (1 km) et VIIRS (375 m) ne donnent pas la même puissance.
    """
    cm = tables.lire(tables.chemin_table(cfg.agregats, "cell_month"),
                     colonnes=["cellule", "annee", "mois", "capteur", "frp_somme"])
    cm["groupe"] = np.where(cm["capteur"] == "Terra", "T", np.where(cm["capteur"] == "Aqua", "A", "V"))
    f = cm.groupby(["cellule", "annee", "mois", "groupe"])["frp_somme"].sum().unstack("groupe", fill_value=0.0)
    for g in ("T", "A", "V"):
        if g not in f:
            f[g] = 0.0
    cle = pd.MultiIndex.from_frame(s[["cellule", "annee", "mois"]])
    f = f.reindex(cle, fill_value=0.0)
    src = source.reindex(cle).astype(str).to_numpy()
    return np.where(np.char.startswith(src.astype("U"), "Terra"), f["T"].to_numpy(),
                    np.where(np.char.startswith(src.astype("U"), "VIIRS"), f["V"].to_numpy(),
                             (f["T"] + f["A"]).to_numpy()))


def _ecrire_index(dossier: Path, mois: pd.DataFrame, tuiles: list[str], pas: float, extra: dict) -> None:
    idx = {
        "format": VERSION_FORMAT,
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "unite": UNITES["modis"],
        "unites": UNITES,
        "carte": {"pas": PAS_CARTE, "modele": "cartes/m_{t}.json"},
        "pas_grille": pas,
        "taille_tuile": TAILLE_TUILE,
        "debut": f"{DEBUT[0]}-{DEBUT[1]:02d}",
        "periode_reference": [2003, 2020],
        "mois": [{"t": int(r.t), "annee": int(r.annee), "mois": int(r.mois), "statut": r.statut,
                  "source": r.source_mois, "couverture": round(float(r.couverture), 3)}
                 for r in mois.itertuples()],
        "tuiles": tuiles,
        **extra,
    }
    (dossier / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))


def publier(cfg: Config, dossier: Path, taille_bloc: float = 10.0) -> None:
    s = tables.lire(tables.chemin_table(cfg.agregats, "harmonized_cell_month"))
    sm = tables.lire(tables.chemin_table(cfg.agregats, "serie_mois"))
    w = equivalent_viirs(cfg, s, taille_bloc)
    cols = ["N_harm", "n_brut"]
    if w is not None:
        s["w"] = w
        cols.append("w")
    else:
        print("conversion_snpp absente : unité équivalent VIIRS non publiée (lancez d'abord calibrer).")
    inc = incertitude(cfg, s, taille_bloc)
    if inc is not None:
        # jour et nuit ont des facteurs indépendants : variances additionnées dans la cellule
        s["e2"], s["f2"] = inc[0] ** 2, inc[1] ** 2
        cols += ["e2", "f2"]
    src = s.groupby(["cellule", "annee", "mois"])["source"].first()
    s = s.groupby(["cellule", "annee", "mois"])[cols].sum().reset_index()
    if inc is not None:
        s["e"], s["f"] = np.sqrt(s.pop("e2")), np.sqrt(s.pop("f2"))
    s["p"] = frp_source(cfg, s, src)
    s["t"] = indice_mois(s["annee"], s["mois"])
    s = s[(s["t"] >= 0) & (s["N_harm"] > 0)].rename(columns={"N_harm": "v", "n_brut": "b"})
    sm["t"] = indice_mois(sm["annee"], sm["mois"])
    sm = sm[sm["t"] >= 0].sort_values("t")
    extra = {}
    val = cfg.journaux / "validation_resultats.csv"
    if val.exists():
        extra["validation"] = json.loads(pd.read_csv(val).to_json(orient="records", force_ascii=False))
    dossier.mkdir(parents=True, exist_ok=True)
    extra["taille_bloc"] = taille_bloc
    # Total mondial harmonisé par mois (équivalent MODIS), lu par la page d'accueil de l'application
    nt = int(sm["t"].max()) + 1 if len(sm) else 0
    tot = s.groupby("t")["v"].sum().reindex(range(nt), fill_value=0.0)
    extra["totaux"] = {"v": [int(round(x)) for x in tot.to_numpy()]}
    tuiles = _ecrire_tuiles(s[["cellule", "t", "v", "b", "p"] + (["w"] if w is not None else [])
                              + (["e", "f"] if inc is not None else [])], dossier, cfg.pas)
    n_cartes = _ecrire_cartes(s, sm[["t", "annee", "mois", "statut"]], dossier, cfg.pas)
    _ecrire_index(dossier, sm, tuiles, cfg.pas, extra)
    print(f"Publication : {len(tuiles)} tuiles, {len(s):,} valeurs, {len(sm)} mois, {n_cartes} cartes -> {dossier}")


def publier_exemple(dossier: Path, pas: float = 0.25, graine: int = 0) -> None:
    """Jeu fictif plausible : saisons des feux décalées selon la latitude, années plus ou moins actives."""
    rng = np.random.default_rng(graine)
    zones = [  # (lat min, lat max, lon min, lon max, intensité, mois du pic)
        (4, 14, -17, 40, 6.0, 1),      # savanes d'Afrique de l'Ouest et centrale (saison sèche boréale)
        (-18, -5, 12, 40, 6.0, 8),     # Afrique australe (saison sèche australe)
        (-15, -3, -60, -40, 3.0, 9),   # Amazonie / Cerrado
        (10, 25, 95, 108, 3.0, 3),     # Asie du Sud-Est
        (-20, -12, 125, 145, 2.5, 10), # Nord de l'Australie
        (55, 65, 90, 130, 1.0, 7),     # Sibérie
    ]
    annees = range(2000, 2027)
    lignes = []
    for la0, la1, lo0, lo1, inten, pic in zones:
        n = int((la1 - la0) * (lo1 - lo0) / pas ** 2 * 0.25)
        lat = rng.uniform(la0, la1, n)
        lon = rng.uniform(lo0, lo1, n)
        cells = np.unique(grille.cellule(lat, lon, pas))
        base = rng.gamma(0.7, inten, len(cells))
        for a in annees:
            fa = rng.lognormal(0, 0.35)
            for m in range(1, 13):
                t = (a - DEBUT[0]) * 12 + (m - DEBUT[1])
                if t < 0 or (a == 2026 and m > 10):
                    continue
                d = min(abs(m - pic), 12 - abs(m - pic))
                saison = math.exp(-(d ** 2) / 3.0)
                lam = base * saison * fa
                v = rng.poisson(lam * 3) / 3.0
                ok = v > 0
                brut = np.round(v[ok] * (6.0 if a >= 2021 else 1.0)).astype(int)
                conv = a >= 2021 or t < 20
                lignes.append(pd.DataFrame({"cellule": cells[ok], "t": t, "v": v[ok], "b": brut, "w": v[ok] * 4.2,
                                            "e": v[ok] * (0.12 if conv else 0.0),
                                            "f": v[ok] * 4.2 * (0.0 if a >= 2021 else 0.12),
                                            "p": brut * rng.gamma(2.0, 6.0 if a >= 2021 else 15.0, ok.sum())}))
    df = pd.concat(lignes, ignore_index=True)
    mois = []
    for a in annees:
        for m in range(1, 13):
            t = (a - DEBUT[0]) * 12 + (m - DEBUT[1])
            if t < 0 or (a == 2026 and m > 10):
                continue
            src = "Terra" if t < 20 else ("MODIS" if a < 2021 else "VIIRS")
            statut = "converti" if src != "MODIS" else "mesuré"
            couv = 0.5 if (a, m) == (2001, 6) else 1.0
            if couv < 0.8:
                statut = "couverture partielle"
            mois.append({"t": t, "annee": a, "mois": m, "statut": statut, "source_mois": src, "couverture": couv})
    dossier.mkdir(parents=True, exist_ok=True)
    tuiles = _ecrire_tuiles(df, dossier, pas)
    n_cartes = _ecrire_cartes(df, pd.DataFrame(mois)[["t", "annee", "mois", "statut"]], dossier, pas)
    validation = [{"methode": "HEXAFIRE", "kappa": 0.645, "fausses_anomalies": 0.157, "biais_median": 0.016,
                   "erreur_mediane": 0.182, "marche_max_annee": 0.066},
                  {"methode": "M1 facteur global", "kappa": 0.543, "fausses_anomalies": 0.236, "biais_median": 0.024,
                   "erreur_mediane": 0.245, "marche_max_annee": 0.108},
                  {"methode": "M0 raccord brut", "kappa": 0.013, "fausses_anomalies": 0.924, "biais_median": 1.946,
                   "erreur_mediane": 1.946, "marche_max_annee": 1.979}]
    _ecrire_index(dossier, pd.DataFrame(mois), tuiles, pas, {"exemple": True, "validation": validation, "taille_bloc": 10.0})
    print(f"Jeu d'EXEMPLE (fictif) : {len(tuiles)} tuiles, {len(df):,} valeurs, {n_cartes} cartes -> {dossier}")
