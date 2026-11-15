# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
"""Étape 5 : validation de l'harmonisation (tests T1, T2, T4 du document de conception).

Principe : validation croisée « une année exclue » sur les années où MODIS et S-NPP
observent ensemble. Pour chaque année y0 :
  1. on estime les facteurs de conversion sans y0 ;
  2. on convertit les détections S-NPP de y0 en équivalent MODIS, comme si MODIS n'existait plus ;
  3. on compare, strate par strate et mois par mois, au vrai MODIS de y0.

Mesures
  T1  kappa de Cohen entre les verdicts « bas / normal / haut » (critère principal) et taux
      de fausses anomalies FA = P(verdict converti != normal | verdict MODIS = normal).
      Un verdict compare le taux du mois (détections / occasions MODIS de la strate) aux
      centiles 10 et 90 du même mois sur 2003-2011 (MODIS seul).
  T2  biais médian et erreur médiane de e = log(1 + N converti) - log(1 + N MODIS).
  T4  moyenne de e par année exclue : pas de marche si |moyenne| < 0,10.

Comparaison à deux méthodes simples (section 8 du document) :
  M0  raccord brut : S-NPP sans conversion (seulement ramené aux occasions MODIS) ;
  M1  correction globale : un seul facteur par période (jour/nuit) pour le monde entier.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import tables
from .config import Config
from .harmonisation import (MODIS, _tables_occasions, base_mensuelle, couples_calibration, estimer_conversion,
                            logistique_groupee, strate_bloc)
from .occasions import passages_par_jour
from . import grille

ANNEES_REF_VERDICT = (2003, 2011)
MIN_ANNEES_REF = 6
MIN_DETECTIONS = 10   # strate-mois trop peu actif : pas de verdict (règle de refus)


def kappa_cohen(a: np.ndarray, b: np.ndarray) -> float:
    cats = np.union1d(a, b)
    po = float(np.mean(a == b))
    pe = float(sum(np.mean(a == c) * np.mean(b == c) for c in cats))
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def verdict(taux: np.ndarray, q10: np.ndarray, q90: np.ndarray) -> np.ndarray:
    return np.where(taux < q10, "bas", np.where(taux > q90, "haut", "normal"))


def _expo_modis_strate(cfg: Config, cellules: np.ndarray, taille_bloc: float, jd: pd.DataFrame) -> pd.DataFrame:
    """Occasions MODIS totales par strate, année et mois : somme_c n_T(c) d_T + somme_c n_A(c) d_A."""
    lat, _ = grille.centre(cellules, cfg.pas)
    st = strate_bloc(cellules, cfg.pas, taille_bloc)
    lignes = []
    for cap in MODIS:
        s_n = pd.Series(passages_par_jour(lat, cap)).groupby(st).sum().rename("s_n").reset_index()
        s_n.columns = ["strate", "s_n"]
        j = jd[jd["capteur"] == cap][["annee", "mois", "jours_disponibles"]]
        x = s_n.merge(j, how="cross")
        x["E"] = x["s_n"] * x["jours_disponibles"]
        lignes.append(x[["strate", "annee", "mois", "E"]])
    return pd.concat(lignes).groupby(["strate", "annee", "mois"])["E"].sum().rename("E_M").reset_index()


def seuils_reference(cfg: Config, base: pd.DataFrame, expo: pd.DataFrame, taille_bloc: float) -> pd.DataFrame:
    a0, a1 = ANNEES_REF_VERDICT
    b = base[base["capteur"].isin(MODIS) & base["annee"].between(a0, a1)].copy()
    b["strate"] = strate_bloc(b["cellule"].to_numpy(), cfg.pas, taille_bloc)
    n = b.groupby(["strate", "annee", "mois"])["n"].sum().rename("N").reset_index()
    r = n.merge(expo, on=["strate", "annee", "mois"], how="inner")
    r["taux"] = r["N"] / r["E_M"]
    q = (r.groupby(["strate", "mois"])["taux"]
           .agg(q10=lambda x: x.quantile(0.10), q90=lambda x: x.quantile(0.90), n_annees="size")
           .reset_index())
    return q[q["n_annees"] >= MIN_ANNEES_REF]


def valider(cfg: Config, taille_bloc: float = 10.0) -> pd.DataFrame:
    base = base_mensuelle(cfg)
    couples = couples_calibration(base, cfg, "S-NPP", MODIS, (cfg.debut_calibration, cfg.fin_calibration))
    annees = sorted(couples["annee"].unique())
    if len(annees) < 2:
        raise SystemExit("Il faut au moins deux années de recouvrement MODIS / S-NPP pour valider.")
    couples["strate"] = strate_bloc(couples["cellule"].to_numpy(), cfg.pas, taille_bloc)

    _, jd = _tables_occasions(cfg)
    cellules = np.unique(base["cellule"].to_numpy())
    expo = _expo_modis_strate(cfg, cellules, taille_bloc, jd)
    seuils = seuils_reference(cfg, base, expo, taille_bloc)
    if seuils.empty:
        raise SystemExit(f"Pas assez d'années MODIS {ANNEES_REF_VERDICT[0]}-{ANNEES_REF_VERDICT[1]} "
                         f"préparées pour établir les seuils des verdicts (au moins {MIN_ANNEES_REF}).")

    resultats = []
    for y0 in annees:
        appr, test = couples[couples["annee"] != y0], couples[couples["annee"] == y0].copy()
        conv = estimer_conversion(cfg, couples=appr, taille_bloc=taille_bloc)
        rg = logistique_groupee(appr["jour_nuit"].astype(str).to_numpy(), appr["y"].to_numpy(dtype="float64"),
                                appr["n"].to_numpy(dtype="float64"), appr["offset"].to_numpy(dtype="float64"))
        a_monde = {str(k): float(v) for k, v in zip(rg["groupe"], rg["alpha"])}
        test = test.merge(conv[["strate", "mois", "jour_nuit", "alpha_stab"]], on=["strate", "mois", "jour_nuit"], how="left")
        jn = test["jour_nuit"].astype(str)
        a_glob = np.array([a_monde.get(x, np.nan) for x in jn], dtype="float64")
        a_loc = test["alpha_stab"].to_numpy(dtype="float64")
        test["alpha_stab"] = np.where(np.isfinite(a_loc), a_loc, a_glob)
        ramene = test["E_ref"] / test["E_p"]                       # S-NPP ramené aux occasions MODIS
        test["H"] = test["y"] * np.exp(-test["alpha_stab"]) * ramene
        test["M0"] = test["y"] * ramene
        test["M1"] = test["y"] * np.exp(-a_glob) * ramene
        agg = test.groupby(["strate", "annee", "mois"])[["N_ref", "H", "M0", "M1"]].sum().reset_index()
        resultats.append(agg)
    r = pd.concat(resultats, ignore_index=True).merge(expo, on=["strate", "annee", "mois"]).merge(
        seuils, on=["strate", "mois"])
    r = r[r["N_ref"] >= MIN_DETECTIONS]
    r["V_MODIS"] = verdict(r["N_ref"] / r["E_M"], r["q10"], r["q90"])

    lignes = []
    for meth in ("H", "M1", "M0"):
        v = verdict(r[meth] / r["E_M"], r["q10"], r["q90"])
        e = np.log1p(r[meth]) - np.log1p(r["N_ref"])
        normal = r["V_MODIS"] == "normal"
        par_annee = e.groupby(r["annee"]).mean()
        lignes.append({
            "methode": {"H": "HEXAFIRE", "M1": "M1 facteur global", "M0": "M0 raccord brut"}[meth],
            "kappa": kappa_cohen(r["V_MODIS"].to_numpy(), v),
            "accord": float(np.mean(v == r["V_MODIS"].to_numpy())),
            "fausses_anomalies": float(np.mean(v[normal.to_numpy()] != "normal")) if normal.any() else np.nan,
            "biais_median": float(np.median(e)),
            "erreur_mediane": float(np.median(np.abs(e))),
            "marche_max_annee": float(par_annee.abs().max()),
        })
    res = pd.DataFrame(lignes)

    # Intervalle de confiance à 95 % de la différence de kappa, par rééchantillonnage des années
    rng = np.random.default_rng(2026)
    ans = r["annee"].unique()
    par_an = {a: r[r["annee"] == a] for a in ans}
    diffs = {"M1": [], "M0": []}
    for _ in range(2000):
        tirage = pd.concat([par_an[a] for a in rng.choice(ans, size=len(ans), replace=True)])
        vM = tirage["V_MODIS"].to_numpy()
        kH = kappa_cohen(vM, verdict(tirage["H"] / tirage["E_M"], tirage["q10"], tirage["q90"]))
        for m in diffs:
            diffs[m].append(kH - kappa_cohen(vM, verdict(tirage[m] / tirage["E_M"], tirage["q10"], tirage["q90"])))
    res["ic95_kappa_H_moins_methode"] = ""
    for m, nom in (("M1", "M1 facteur global"), ("M0", "M0 raccord brut")):
        lo, hi = np.nanpercentile(diffs[m], [2.5, 97.5])
        res.loc[res["methode"] == nom, "ic95_kappa_H_moins_methode"] = f"[{lo:.3f} ; {hi:.3f}]"
    res["n_strate_mois"] = len(r)
    res["annees_testees"] = ",".join(map(str, annees))

    cfg.journaux.mkdir(parents=True, exist_ok=True)
    res.to_csv(cfg.journaux / "validation_resultats.csv", index=False)
    r.to_csv(cfg.journaux / "validation_detail.csv.gz", index=False)
    cibles = {"kappa": ">= 0.5", "fausses_anomalies": "<= 0.15", "biais_median": "|.| < 0.10",
              "erreur_mediane": "< 0.25", "marche_max_annee": "< 0.10"}
    with open(cfg.journaux / "validation_cibles.json", "w", encoding="utf-8") as f:
        json.dump(cibles, f, ensure_ascii=False, indent=1)

    print(f"Validation « une année exclue » sur {', '.join(map(str, annees))} : {len(r):,} strate-mois comparés")
    pd.set_option("display.width", 140)
    print(res.drop(columns=["n_strate_mois", "annees_testees"]).round(3).to_string(index=False))
    if len(ans) < 4:
        print(f"  (intervalles de confiance indicatifs : seulement {len(ans)} année(s) testée(s))")
    print("Règle de supériorité : HEXAFIRE est meilleur que M1 si tout l'intervalle de kappa_H - kappa_M1 est > 0.")
    print("Cibles (T1, T2, T4) : kappa >= 0,5 ; fausses anomalies <= 0,15 ; |biais| < 0,10 ; "
          "erreur médiane < 0,25 ; marche annuelle < 0,10")
    return res
