"""Étape 4 : conversion VIIRS -> MODIS et série harmonisée.

Modèle (section 5 du document de conception)
--------------------------------------------
Pour une cellule-mois observée par MODIS (Terra + Aqua, noté M) et par une plateforme
VIIRS p, conditionnellement au total n = N_M + N_p :

    N_p | n ~ Binomiale(n, pi),   logit(pi) = alpha + log(E_p / E_M)

L'activité réelle des feux disparaît. alpha mesure l'écart de sensibilité entre p et
MODIS à occasions égales : un point chaud VIIRS vaut exp(-alpha) point chaud MODIS.
alpha est estimé par strate r, mois de l'année k et période d (jour/nuit), par maximum
de vraisemblance (Newton, vectorisé par groupe). La surdispersion est prise en compte
par un facteur quasi-binomial (statistique de Pearson). Les estimations de chaque
mois sont ensuite rapprochées de la valeur annuelle de la strate (DerSimonian-Laird).

Strates
-------
En attendant les régions GFED et la couverture du sol, une strate est un bloc
régulier de `taille_bloc` degrés (10° par défaut). Le module est écrit pour qu'une
autre définition de strate (table cellule -> strate) puisse être branchée ensuite.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import grille, tables
from .occasions import passages_par_jour
from .config import Config

MODIS = ("Terra", "Aqua")
SEUIL_COUVERTURE = 0.8


# --------------------------------------------------------------------------- strates
def strate_bloc(cellules: np.ndarray, pas: float, taille_bloc: float) -> np.ndarray:
    lat, lon = grille.centre(cellules, pas)
    n_lon = int(round(360 / taille_bloc))
    lig = np.floor((90.0 - lat) / taille_bloc).astype("int64")
    col = np.floor((lon + 180.0) / taille_bloc).astype("int64")
    return lig * n_lon + col


# --------------------------------------------------------------------------- données
def _tables_occasions(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    pc = tables.lire(tables.chemin_table(cfg.agregats, "passages_cellule"))
    jd = tables.lire(tables.chemin_table(cfg.agregats, "jours_disponibles"))
    return pc, jd


def occasions_lignes(df: pd.DataFrame, capteurs: tuple[str, ...], pc: pd.DataFrame, jd: pd.DataFrame,
                     pas: float = 0.25) -> pd.DataFrame:
    """Renvoie (E, E_attendu) pour chaque ligne (cellule, annee, mois) de df, sommés sur `capteurs`.

    E = passages/jour de la cellule x jours disponibles du capteur ce mois-là. Les passages/jour sont
    recalculés à partir de la latitude (toujours à jour, même pour une cellule apparue depuis le
    dernier `occasions`). Un mois absent de jours_disponibles donne E = 0 (donc exclu en aval).
    Calcul ligne à ligne : on ne construit jamais la table complète cellule x mois.
    """
    E = np.zeros(len(df))
    Ea = np.zeros(len(df))
    lat, _ = grille.centre(df["cellule"].to_numpy(), pas)
    cle = df[["annee", "mois"]].reset_index(drop=True)
    for cap in capteurs:
        nj = passages_par_jour(lat, cap)
        x = cle.merge(jd[jd["capteur"] == cap][["annee", "mois", "jours_disponibles", "jours_mois"]],
                      on=["annee", "mois"], how="left")
        E += nj * x["jours_disponibles"].fillna(0).to_numpy(dtype="float64")
        Ea += nj * x["jours_mois"].fillna(0).to_numpy(dtype="float64")
    return pd.DataFrame({"E": E, "E_attendu": Ea}, index=df.index)


def base_mensuelle(cfg: Config) -> pd.DataFrame:
    """Comptages et occasions par cellule, mois, capteur et période."""
    return tables.lire(tables.chemin_table(cfg.agregats, "cell_month"),
                       colonnes=["cellule", "annee", "mois", "capteur", "jour_nuit", "n"])


def couples_calibration(base: pd.DataFrame, cfg: Config, plateforme: str, reference: tuple[str, ...],
                        annees: tuple[int, int]) -> pd.DataFrame:
    """Couples (cellule, mois, période) où la référence et la plateforme ont toutes deux observé.

    Retourne y = N_plateforme, n = N_ref + N_plateforme, E_ref, E_p.
    Les occasions de la référence sont la somme de celles de ses capteurs (Terra + Aqua).
    """
    a0, a1 = annees
    b = base[base["annee"].between(a0, a1)]
    cles = ["cellule", "annee", "mois", "jour_nuit"]

    ref = b[b["capteur"].isin(reference)]
    ref = ref.groupby(cles).agg(N_ref=("n", "sum")).reset_index()
    p = b[b["capteur"] == plateforme].groupby(cles).agg(N_p=("n", "sum")).reset_index()
    d = ref.merge(p, on=cles, how="outer").fillna({"N_ref": 0, "N_p": 0})

    pc, jd = _tables_occasions(cfg)
    er = occasions_lignes(d, reference, pc, jd, cfg.pas)
    ep = occasions_lignes(d, (plateforme,), pc, jd, cfg.pas)
    d["E_ref"], d["Ea_ref"], d["E_p"], d["Ea_p"] = er["E"], er["E_attendu"], ep["E"], ep["E_attendu"]
    ok = ((d["Ea_ref"] > 0) & (d["Ea_p"] > 0) & (d["E_ref"] > 0) & (d["E_p"] > 0)
          & (d["E_ref"] >= SEUIL_COUVERTURE * d["Ea_ref"]) & (d["E_p"] >= SEUIL_COUVERTURE * d["Ea_p"])
          & ((d["N_ref"] + d["N_p"]) >= 1))
    exclus_sans_occasions = int(((d["E_ref"] <= 0) | (d["E_p"] <= 0)).sum())
    if exclus_sans_occasions:
        mois_manquants = sorted(set(map(tuple, d.loc[(d["E_ref"] <= 0) | (d["E_p"] <= 0), ["annee", "mois"]]
                                        .drop_duplicates().to_numpy().tolist())))
        print(f"  attention : {exclus_sans_occasions:,} couples sans occasions connues, exclus "
              f"(mois absents de jours_disponibles : {mois_manquants[:6]}{' ...' if len(mois_manquants) > 6 else ''}). "
              f"Relancez `python -m hexafire occasions` après chaque `agreger`.")
    d = d.loc[ok].copy()
    d["y"] = d["N_p"].astype("float64")
    d["n"] = (d["N_ref"] + d["N_p"]).astype("float64")
    d["offset"] = np.log(d["E_p"] / d["E_ref"])
    return d


# --------------------------------------------------------------------------- estimation
def logistique_groupee(groupe: np.ndarray, y: np.ndarray, n: np.ndarray, offset: np.ndarray,
                       iterations: int = 50) -> pd.DataFrame:
    """MLE de alpha_g dans logit(pi) = alpha_g + offset, par groupe, avec dispersion quasi-binomiale."""
    fini = np.isfinite(offset) & np.isfinite(y) & np.isfinite(n) & (n > 0)
    groupe, y, n, offset = groupe[fini], y[fini], n[fini], offset[fini]
    g_codes, g = np.unique(groupe, return_inverse=True)
    G = len(g_codes)
    sy, sn = np.bincount(g, y, G), np.bincount(g, n, G)
    m = np.bincount(g, minlength=G).astype("float64")
    prop = np.clip(sy / np.maximum(sn, 1e-12), 1e-6, 1 - 1e-6)
    alpha = np.log(prop / (1 - prop)) - np.bincount(g, offset * n, G) / np.maximum(sn, 1e-12)
    for _ in range(iterations):
        pi = 1.0 / (1.0 + np.exp(-(alpha[g] + offset)))
        U = np.bincount(g, y - n * pi, G)
        I = np.bincount(g, n * pi * (1 - pi), G)
        pas = np.where(I > 0, U / np.maximum(I, 1e-12), 0.0)
        alpha += np.clip(pas, -5, 5)
        if np.max(np.abs(pas)) < 1e-9:
            break
    pi = 1.0 / (1.0 + np.exp(-(alpha[g] + offset)))
    I = np.bincount(g, n * pi * (1 - pi), G)
    pearson = np.bincount(g, (y - n * pi) ** 2 / np.maximum(n * pi * (1 - pi), 1e-12), G)
    phi = np.where(m > 1, np.maximum(pearson / np.maximum(m - 1, 1), 1.0), np.nan)
    se = np.sqrt(phi / np.maximum(I, 1e-12))
    degenere = (sy <= 0) | (sy >= sn) | (m < 3)
    se[degenere] = np.inf
    return pd.DataFrame({"groupe": g_codes, "alpha": alpha, "se": se, "dispersion": phi,
                         "n_couples": m.astype("int64"), "n_viirs": sy, "n_total": sn})


def dersimonian_laird(alpha_k: np.ndarray, se_k: np.ndarray) -> float:
    ok = np.isfinite(se_k) & (se_k > 0) & np.isfinite(alpha_k)
    if ok.sum() < 2:
        return 0.0
    w = 1 / se_k[ok] ** 2
    a = alpha_k[ok]
    abar = np.sum(w * a) / np.sum(w)
    Q = np.sum(w * (a - abar) ** 2)
    denom = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    return float(max(0.0, (Q - (ok.sum() - 1)) / denom)) if denom > 0 else 0.0


def estimer_conversion(cfg: Config, plateforme: str = "S-NPP", reference: tuple[str, ...] = MODIS,
                       annees: tuple[int, int] | None = None, taille_bloc: float = 10.0,
                       couples: pd.DataFrame | None = None) -> pd.DataFrame:
    """alpha stabilisé par strate, mois de l'année et période."""
    annees = annees or (cfg.debut_calibration, cfg.fin_calibration)
    if couples is None:
        couples = couples_calibration(base_mensuelle(cfg), cfg, plateforme, reference, annees)
    c = couples.copy()
    c["strate"] = strate_bloc(c["cellule"].to_numpy(), cfg.pas, taille_bloc)

    # 1) par strate x mois de l'année x période
    cle_k = c["strate"].astype(str) + "|" + c["mois"].astype(str) + "|" + c["jour_nuit"]
    rk = logistique_groupee(cle_k.to_numpy(), c["y"].to_numpy(), c["n"].to_numpy(), c["offset"].to_numpy())
    rk[["strate", "mois", "jour_nuit"]] = rk["groupe"].str.split("|", expand=True)
    rk["strate"], rk["mois"] = rk["strate"].astype("int64"), rk["mois"].astype("int64")

    # 2) par strate x période (toutes saisons) : valeur vers laquelle on rapproche
    cle_r = c["strate"].astype(str) + "|" + c["jour_nuit"]
    rr = logistique_groupee(cle_r.to_numpy(), c["y"].to_numpy(), c["n"].to_numpy(), c["offset"].to_numpy())
    rr[["strate", "jour_nuit"]] = rr["groupe"].str.split("|", expand=True)
    rr["strate"] = rr["strate"].astype("int64")

    # 3) par période, monde entier : dernier recours pour une strate dégénérée
    rg = logistique_groupee(c["jour_nuit"].to_numpy(), c["y"].to_numpy(), c["n"].to_numpy(), c["offset"].to_numpy())
    alpha_monde = {str(k): float(v) for k, v in zip(rg["groupe"], rg["alpha"])}

    def vers_monde(periodes: pd.Series) -> np.ndarray:
        # conversion explicite en float : évite les erreurs de type avec les chaînes Arrow (pyarrow)
        return np.array([alpha_monde.get(str(p), np.nan) for p in periodes], dtype="float64")

    degenere = ~np.isfinite(rr["se"].to_numpy(dtype="float64"))
    rr["alpha"] = np.where(degenere, vers_monde(rr["jour_nuit"]), rr["alpha"].to_numpy(dtype="float64"))

    rk = rk.merge(rr[["strate", "jour_nuit", "alpha", "se"]].rename(columns={"alpha": "alpha_r", "se": "se_r"}),
                  on=["strate", "jour_nuit"], how="left")
    ar = rk["alpha_r"].to_numpy(dtype="float64")
    rk["alpha_r"] = np.where(np.isfinite(ar), ar, vers_monde(rk["jour_nuit"]))
    tau2 = {k: dersimonian_laird(g["alpha"].to_numpy(), g["se"].to_numpy())
            for k, g in rk.groupby(["strate", "jour_nuit"])}
    rk["tau2"] = [tau2[(s, d)] for s, d in zip(rk["strate"], rk["jour_nuit"])]
    w = np.where(np.isfinite(rk["se"]), rk["tau2"] / (rk["tau2"] + rk["se"] ** 2), 0.0)
    rk["poids_local"] = np.nan_to_num(w)
    rk["alpha_stab"] = rk["poids_local"] * rk["alpha"].where(np.isfinite(rk["se"]), 0) \
        + (1 - rk["poids_local"]) * rk["alpha_r"]
    rk["facteur_viirs_vers_modis"] = np.exp(-rk["alpha_stab"])
    rk["plateforme"] = plateforme
    rk["taille_bloc"] = taille_bloc
    return rk.drop(columns=["groupe"])


RELAIS = {"NOAA-20": (2018, 2026), "NOAA-21": (2023, 2026)}
VIIRS = ("S-NPP", "NOAA-20", "NOAA-21")


def calibrer_relais(cfg: Config, base: pd.DataFrame, conv_snpp: pd.DataFrame, taille_bloc: float) -> None:
    """NOAA-20 et NOAA-21 raccordés à S-NPP : alpha_p = alpha_S-NPP + delta_p (estimé face à S-NPP)."""
    for plat, annees in RELAIS.items():
        couples = couples_calibration(base, cfg, plat, ("S-NPP",), annees)
        if couples.empty or couples["annee"].nunique() < 1:
            print(f"  {plat} : pas encore de recouvrement avec S-NPP, relais non calculé")
            continue
        delta = estimer_conversion(cfg, couples=couples, taille_bloc=taille_bloc, plateforme=plat)
        d = delta[["strate", "mois", "jour_nuit", "alpha_stab"]].rename(columns={"alpha_stab": "delta"})
        c = conv_snpp[["strate", "mois", "jour_nuit", "alpha_stab"]].merge(d, on=["strate", "mois", "jour_nuit"], how="left")
        delta_monde = d.groupby("jour_nuit")["delta"].median()
        dm = np.array([delta_monde.get(str(x), 0.0) for x in c["jour_nuit"].astype(str)], dtype="float64")
        dv = c["delta"].to_numpy(dtype="float64")
        c["delta"] = np.where(np.isfinite(dv), dv, dm)
        c["alpha_stab"] = c["alpha_stab"] + c["delta"]
        c["facteur_viirs_vers_modis"] = np.exp(-c["alpha_stab"])
        c["plateforme"] = plat
        nom = "conversion_" + plat.lower().replace("-", "")
        tables.ecrire(c, tables.chemin_table(cfg.agregats, nom))
        med = np.exp(-c["delta"]).groupby(c["jour_nuit"]).median()
        print(f"  {plat} raccordé à S-NPP sur {sorted(couples['annee'].unique())} : "
              f"1 point chaud {plat} = {med.get('J', np.nan):.3f} (jour) / {med.get('N', np.nan):.3f} (nuit) point chaud S-NPP")


def calibrer(cfg: Config, taille_bloc: float = 10.0) -> pd.DataFrame:
    base = base_mensuelle(cfg)
    couples = couples_calibration(base, cfg, "S-NPP", MODIS, (cfg.debut_calibration, cfg.fin_calibration))
    if couples.empty:
        raise SystemExit("Aucun couple MODIS / S-NPP sur la période de calibration : "
                         "préparez et agrégez d'abord des mois S-NPP de 2012-2020.")
    conv = estimer_conversion(cfg, couples=couples, taille_bloc=taille_bloc)
    sortie = tables.ecrire(conv, tables.chemin_table(cfg.agregats, "conversion_snpp"))

    annees = sorted(couples["annee"].unique())
    print(f"Calibration S-NPP -> MODIS sur {annees[0]}-{annees[-1]} ({len(annees)} année(s)), "
          f"{len(couples):,} couples cellule-mois, {conv['strate'].nunique()} strates")
    for d, g in conv.groupby("jour_nuit"):
        f = g["facteur_viirs_vers_modis"]
        print(f"  {'jour' if d == 'J' else 'nuit'} : 1 point chaud S-NPP = {f.median():.3f} point chaud MODIS "
              f"(médiane des strates ; 10 %-90 % : {f.quantile(.1):.3f}-{f.quantile(.9):.3f})")
    print(f"  -> {sortie}")
    calibrer_relais(cfg, base, conv, taille_bloc)
    return conv


# --------------------------------------------------------------------------- série harmonisée
def construire_serie(cfg: Config, taille_bloc: float = 10.0) -> pd.DataFrame:
    """Série harmonisée en équivalent MODIS (tableau 5 du document de conception).

    nov. 2000 - juin 2002 : Terra seul, ramené à Terra + Aqua par exp(-gamma)
    juil. 2002 - déc. 2020 : Terra + Aqua (mesuré)
    à partir de janv. 2021 : VIIRS converti par exp(-alpha)
    Chaque valeur est ramenée à l'exposition de référence E_ref (médiane 2003-2020 de E_MODIS).
    Stockage creux : seules les cellules-mois avec au moins une détection sont écrites ; un mois
    observé sans ligne pour une cellule vaut 0. Le statut du mois est dans serie_mois.
    """
    conv = tables.lire(tables.chemin_table(cfg.agregats, "conversion_snpp"))
    cm = tables.lire(tables.chemin_table(cfg.agregats, "cell_month"),
                     colonnes=["cellule", "annee", "mois", "capteur", "jour_nuit", "n"])
    pc, jd = _tables_occasions(cfg)
    a_bascule, m_bascule = (int(x) for x in cfg.bascule_viirs.split("-"))
    t = cm["annee"] * 100 + cm["mois"]
    bascule = a_bascule * 100 + m_bascule
    r0, r1 = cfg.debut_reference, cfg.fin_reference

    # Exposition de référence : médiane sur 2003-2020 de E_MODIS = n_T(c) d_T(y,k) + n_A(c) d_A(y,k)
    cells = np.unique(cm["cellule"].to_numpy())
    nT = pc[pc["capteur"] == "Terra"].set_index("cellule")["n_jour"].reindex(cells).fillna(0).to_numpy()
    nA = pc[pc["capteur"] == "Aqua"].set_index("cellule")["n_jour"].reindex(cells).fillna(0).to_numpy()
    jr = jd[jd["annee"].between(r0, r1)]
    lignes_ref = []
    for k in range(1, 13):
        dT = jr[(jr["capteur"] == "Terra") & (jr["mois"] == k)].set_index("annee")["jours_disponibles"]
        dA = jr[(jr["capteur"] == "Aqua") & (jr["mois"] == k)].set_index("annee")["jours_disponibles"]
        ans = sorted(set(dT.index) | set(dA.index))
        if not ans:
            continue
        dT, dA = dT.reindex(ans).fillna(0).to_numpy(), dA.reindex(ans).fillna(0).to_numpy()
        E = np.outer(nT, dT) + np.outer(nA, dA)           # cellules x années (petit : une colonne par an)
        lignes_ref.append(pd.DataFrame({"cellule": cells, "mois": k, "E_ref": np.median(E, axis=1)}))
    e_ref = pd.concat(lignes_ref, ignore_index=True)

    # gamma : Terra face à Terra + Aqua, par strate, mois de l'année et période (2003-2020).
    # Les occasions se séparent : somme sur cellules et années = (somme des n(c)) x (somme des jours).
    b = cm[cm["annee"].between(r0, r1) & cm["capteur"].isin(MODIS)].copy()
    b["strate"] = strate_bloc(b["cellule"].to_numpy(), cfg.pas, taille_bloc)
    st = strate_bloc(cells, cfg.pas, taille_bloc)
    somme_nT = pd.Series(nT).groupby(st).sum()
    somme_nA = pd.Series(nA).groupby(st).sum()
    jT = jr[jr["capteur"] == "Terra"].groupby("mois")["jours_disponibles"].sum()
    jA = jr[jr["capteur"] == "Aqua"].groupby("mois")["jours_disponibles"].sum()
    g = b.groupby(["strate", "mois", "jour_nuit"]).apply(
        lambda x: pd.Series({"nT": x.loc[x["capteur"] == "Terra", "n"].sum(), "nM": x["n"].sum()}),
        include_groups=False).reset_index()
    g["eT"] = g["strate"].map(somme_nT).fillna(0) * g["mois"].map(jT).fillna(0)
    g["eM"] = g["eT"] + g["strate"].map(somme_nA).fillna(0) * g["mois"].map(jA).fillna(0)
    g = g[(g["eT"] > 0) & (g["eM"] > 0)]
    g["gamma"] = np.log(((g["nT"] + 0.5) / g["eT"]) / ((g["nM"] + 0.5) / g["eM"]))
    tables.ecrire(g, tables.chemin_table(cfg.agregats, "conversion_terra"))

    morceaux = []
    # Période 1 : Terra seul
    p1 = cm[(t < 200207) & (cm["capteur"] == "Terra")].copy()
    p1["E"] = occasions_lignes(p1, ("Terra",), pc, jd, cfg.pas)["E"]
    p1["strate"] = strate_bloc(p1["cellule"].to_numpy(), cfg.pas, taille_bloc)
    p1 = p1.merge(g[["strate", "mois", "jour_nuit", "gamma"]], on=["strate", "mois", "jour_nuit"], how="left")
    p1["facteur"] = np.exp(-p1["gamma"].fillna(0.0)) / p1["E"]
    p1["source"] = "Terra (converti)"
    morceaux.append(p1)
    # Mois postérieurs à la bascule : VIIRS (S-NPP, NOAA-20, NOAA-21 raccordés) s'il est disponible,
    # sinon MODIS « provisoire » (en attendant le téléchargement de VIIRS).
    convs = {"S-NPP": conv}
    for plat in ("NOAA-20", "NOAA-21"):
        ch = tables.chemin_table(cfg.agregats, "conversion_" + plat.lower().replace("-", ""))
        if ch.exists():
            convs[plat] = tables.lire(ch)
    vd = jd[jd["capteur"].isin(list(convs)) & (jd["jours_disponibles"] > 0)]
    mois_viirs = set((vd["annee"] * 100 + vd["mois"]).tolist())
    mois_snpp = mois_viirs   # nom conservé pour le calcul des statuts plus bas
    apres = t >= bascule
    via_viirs = apres & t.isin(mois_viirs)
    via_modis_prov = apres & ~t.isin(mois_viirs)

    # Période 2 : Terra + Aqua (mesuré), et MODIS provisoire après la bascule si pas de S-NPP
    for masque, etiquette in (((t >= 200207) & (t < bascule), "MODIS (mesuré)"),
                              (via_modis_prov, "MODIS (provisoire, en attendant VIIRS)")):
        p2 = (cm[masque & cm["capteur"].isin(MODIS)]
              .groupby(["cellule", "annee", "mois", "jour_nuit"])["n"].sum().reset_index())
        if p2.empty:
            continue
        p2["E"] = occasions_lignes(p2, MODIS, pc, jd, cfg.pas)["E"]
        p2["facteur"] = 1.0 / p2["E"]
        p2["source"] = etiquette
        morceaux.append(p2)
    # Période 3 : VIIRS converti ; plusieurs plateformes actives = moyenne pondérée par les occasions
    #   N_harm = (somme_p N_p exp(-alpha_p)) / (somme_p E_p) * E_ref   (aucune addition brute de plateformes)
    v = cm[via_viirs & cm["capteur"].isin(list(convs))].copy()
    if not v.empty:
        v["strate"] = strate_bloc(v["cellule"].to_numpy(), cfg.pas, taille_bloc)
        parts = []
        for plat, cv in convs.items():
            x = v[v["capteur"] == plat].merge(cv[["strate", "mois", "jour_nuit", "alpha_stab"]],
                                               on=["strate", "mois", "jour_nuit"], how="left")
            a = x["alpha_stab"].to_numpy(dtype="float64")
            x["num"] = x["n"] * np.exp(-np.where(np.isfinite(a), a, np.nanmedian(cv["alpha_stab"])))
            parts.append(x[["cellule", "annee", "mois", "jour_nuit", "n", "num"]])
        p3 = pd.concat(parts).groupby(["cellule", "annee", "mois", "jour_nuit"])[["n", "num"]].sum().reset_index()
        p3["E"] = occasions_lignes(p3, tuple(convs), pc, jd, cfg.pas)["E"]   # somme des E des plateformes actives
        p3["facteur"] = (p3["num"] / p3["n"]) / p3["E"]
        p3["source"] = "VIIRS (converti)"
        morceaux.append(p3)
    morceaux = [m for m in morceaux if not m.empty]

    s = pd.concat([m[["cellule", "annee", "mois", "jour_nuit", "n", "facteur", "source"]] for m in morceaux],
                  ignore_index=True).merge(e_ref, on=["cellule", "mois"], how="left")
    s["E_ref"] = s["E_ref"].fillna(s["E_ref"].median())
    s["poids"] = s["facteur"] * s["E_ref"]          # poids d'une détection de cette cellule-mois
    s["N_harm"] = s["n"] * s["poids"]
    s = s.drop(columns=["facteur"]).rename(columns={"n": "n_brut"})
    sortie = tables.ecrire(s, tables.chemin_table(cfg.agregats, "harmonized_cell_month"))

    # Statut global de chaque mois selon la couverture de sa source
    jd = jd.copy()
    jd["t"] = jd["annee"] * 100 + jd["mois"]
    src = np.where(jd["t"] < 200207, "Terra",
                   np.where(jd["t"] < bascule, "MODIS",
                            np.where(jd["t"].isin(mois_viirs), "VIIRS", "MODIS provisoire")))
    jd["source_mois"] = src
    keep = ((src == "Terra") & (jd["capteur"] == "Terra")) \
        | (np.isin(src, ["MODIS", "MODIS provisoire"]) & jd["capteur"].isin(MODIS)) \
        | ((src == "VIIRS") & jd["capteur"].isin(list(convs)))
    sm = jd[keep].groupby(["annee", "mois", "source_mois"])[["jours_disponibles", "jours_mois"]].sum().reset_index()
    sm["couverture"] = sm["jours_disponibles"] / sm["jours_mois"]
    sm["statut"] = np.select([sm["couverture"] < 0.3, sm["couverture"] < 0.8], ["non observé", "couverture partielle"],
                             np.select([sm["source_mois"] == "MODIS", sm["source_mois"] == "MODIS provisoire"],
                                       ["mesuré", "provisoire"], "converti"))
    tables.ecrire(sm, tables.chemin_table(cfg.agregats, "serie_mois"))
    print(f"Série harmonisée : {len(s):,} cellules-mois non nulles, {s['N_harm'].sum():,.0f} points chauds "
          f"équivalent MODIS -> {sortie}")
    print(sm["statut"].value_counts().to_string())
    return s
