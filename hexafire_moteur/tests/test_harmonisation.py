# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
import numpy as np
import pandas as pd

from hexafire import grille
from hexafire.config import Config
from hexafire.harmonisation import estimer_conversion, logistique_groupee


def cfg0():
    from pathlib import Path
    p = Path("/tmp")
    return Config(p, p, p, p, 0.25, (0,), 30, ("l",), 2003, 2020, 2012, 2020, "2021-01")


def test_logistique_retrouve_alpha():
    rng = np.random.default_rng(1)
    m = 4000
    g = rng.integers(0, 3, m)
    vrai = np.array([np.log(3.0), np.log(6.0), np.log(1.5)])
    lam = rng.gamma(0.8, 20, m)
    E_M, E_p = rng.uniform(20, 30, m), rng.uniform(25, 40, m)
    N_M = rng.poisson(lam * E_M / 25)
    N_p = rng.poisson(lam * E_p / 25 * np.exp(vrai[g]))
    n = N_M + N_p
    ok = n > 0
    r = logistique_groupee(g[ok], N_p[ok].astype(float), n[ok].astype(float), np.log(E_p / E_M)[ok])
    assert np.allclose(r["alpha"].to_numpy(), vrai, atol=0.05)
    assert np.all(np.isfinite(r["se"]))


def test_conversion_par_strate_et_periode():
    rng = np.random.default_rng(2)
    # deux blocs de 10° : Afrique de l'Ouest (lat 8, lon 2) et Sibérie (lat 62, lon 100)
    cellA = grille.cellule(np.full(300, 8.0) + rng.uniform(-2, 2, 300), np.full(300, 2.0) + rng.uniform(-2, 2, 300))
    cellB = grille.cellule(np.full(300, 62.0) + rng.uniform(-2, 2, 300), np.full(300, 100.0) + rng.uniform(-2, 2, 300))
    vrai = {("A", "J"): np.log(4.0), ("A", "N"): np.log(15.0), ("B", "J"): np.log(1.5), ("B", "N"): np.log(3.0)}
    lignes = []
    for nom, cells in (("A", cellA), ("B", cellB)):
        for c in cells:
            for annee in range(2012, 2021):
                for mois in (1, 7):
                    for d in ("J", "N"):
                        lam = rng.gamma(1.0, 10)
                        E_ref, E_p = 50.0, 64.0
                        nm = rng.poisson(lam * E_ref / 50)
                        npp = rng.poisson(lam * E_p / 50 * np.exp(vrai[(nom, d)]))
                        if nm + npp:
                            lignes.append((c, annee, mois, d, npp, nm + npp, np.log(E_p / E_ref), nom))
    couples = pd.DataFrame(lignes, columns=["cellule", "annee", "mois", "jour_nuit", "y", "n", "offset", "nom"])
    conv = estimer_conversion(cfg0(), couples=couples)
    from hexafire.harmonisation import strate_bloc
    sA = strate_bloc(np.array([grille.cellule(8.0, 2.0)]), 0.25, 10.0)[0]
    for (nom, d), a in vrai.items():
        s = sA if nom == "A" else strate_bloc(np.array([grille.cellule(62.0, 100.0)]), 0.25, 10.0)[0]
        sel = conv[(conv["strate"] == s) & (conv["jour_nuit"] == d)]
        assert np.allclose(sel["alpha_stab"], a, atol=0.08), (nom, d, sel["alpha_stab"].tolist(), a)


def test_chaine_calibrer(tmp_path):
    from hexafire import tables
    from hexafire.harmonisation import calibrer
    from hexafire.occasions import passages_par_jour
    cfg = Config(tmp_path, tmp_path, tmp_path, tmp_path, 0.25, (0,), 30, ("l",), 2003, 2020, 2012, 2020, "2021-01")
    rng = np.random.default_rng(3)
    cells = np.unique(grille.cellule(rng.uniform(5, 12, 400), rng.uniform(0, 8, 400)))
    lat, _ = grille.centre(cells)
    pc = pd.concat([pd.DataFrame({"cellule": cells, "capteur": c, "n_jour": passages_par_jour(lat, c)})
                    for c in ("Terra", "Aqua", "S-NPP")])
    jd = pd.DataFrame([(c, a, m, 30, 30 if not (c == "Aqua" and a == 2015 and m == 3) else 10)
                       for c in ("Terra", "Aqua", "S-NPP") for a in range(2012, 2021) for m in range(1, 13)],
                      columns=["capteur", "annee", "mois", "jours_mois", "jours_disponibles"])
    tables.ecrire(pc, tables.chemin_table(tmp_path, "passages_cellule"))
    tables.ecrire(jd, tables.chemin_table(tmp_path, "jours_disponibles"))
    n_j = dict(zip(zip(pc["cellule"], pc["capteur"]), pc["n_jour"]))
    lignes = []
    for c in cells:
        for a in range(2012, 2021):
            for m in (1, 2, 12):
                lam = rng.gamma(1.0, 0.05)
                for d, fac in (("J", 4.0), ("N", 12.0)):
                    for cap, f in (("Terra", 1.0), ("Aqua", 1.0), ("S-NPP", fac)):
                        n = rng.poisson(lam * n_j[(c, cap)] * 30 * f)
                        if n:
                            lignes.append((c, a, m, cap, d, n, 0.0))
    cm = pd.DataFrame(lignes, columns=["cellule", "annee", "mois", "capteur", "jour_nuit", "n", "frp_somme"])
    tables.ecrire(cm, tables.chemin_table(tmp_path, "cell_month"))
    conv = calibrer(cfg)
    assert np.isfinite(conv["se_stab"]).all() and (conv["se_stab"] > 0).all()
    fac = conv.groupby("jour_nuit")["facteur_viirs_vers_modis"].median()
    assert abs(fac["J"] - 1 / 4) < 0.02 and abs(fac["N"] - 1 / 12) < 0.01


def test_serie_apres_calibrage(tmp_path):
    test_chaine_calibrer(tmp_path)
    from hexafire import tables
    from hexafire.harmonisation import construire_serie
    cfg = Config(tmp_path, tmp_path, tmp_path, tmp_path, 0.25, (0,), 30, ("l",), 2012, 2020, 2012, 2020, "2016-01")
    s = construire_serie(cfg)
    # Après la bascule (fictive en 2016 ici), S-NPP converti doit retomber au niveau de MODIS
    avant = s[(s["annee"] < 2016)].groupby("annee")["N_harm"].sum().mean()
    apres = s[(s["annee"] >= 2016)].groupby("annee")["N_harm"].sum().mean()
    assert 0.85 < apres / avant < 1.15
    assert set(s["source"]) == {"MODIS (mesuré)", "VIIRS (converti)"}
    # L'équivalent VIIRS publié est l'inverse de la conversion : il retrouve les détections S-NPP brutes
    from hexafire.publication import equivalent_viirs
    w = equivalent_viirs(cfg, s)
    v = s["source"] == "VIIRS (converti)"
    assert 0.9 < w[v].sum() / s.loc[v, "n_brut"].sum() < 1.1
    # Incertitude de conversion : nulle pour MODIS mesuré en équivalent MODIS, positive pour VIIRS converti,
    # et inversement en équivalent VIIRS
    from hexafire.publication import incertitude
    e, f = incertitude(cfg, s)
    m = s["source"].str.startswith("MODIS")
    assert (e[m] == 0).all() and (e[v] > 0).all() and np.isfinite(e).all()
    assert (f[v] == 0).all() and (f[m] > 0).all()
    assert (e[v] / s.loc[v, "N_harm"]).median() < 0.5
    # Publication complète : la FRP de la source du mois est écrite dans les tuiles
    import json
    from hexafire.publication import publier
    publier(cfg, tmp_path / "site")
    idx = json.loads((tmp_path / "site" / "index.json").read_text())
    tu = json.loads((tmp_path / "site" / "tuiles" / f"t_{idx['tuiles'][0]}.json").read_text())
    assert len(tu["p"]) == len(tu["b"]) and all(x >= 0 for x in tu["p"])


def test_calibrer_mois_sans_occasions(tmp_path):
    """Un mois S-NPP présent dans cell_month mais absent de jours_disponibles ne doit pas tout casser."""
    test_chaine_calibrer(tmp_path)
    from hexafire import tables
    from hexafire.harmonisation import calibrer
    cfg = Config(tmp_path, tmp_path, tmp_path, tmp_path, 0.25, (0,), 30, ("l",), 2003, 2020, 2012, 2020, "2021-01")
    jd = tables.lire(tables.chemin_table(tmp_path, "jours_disponibles"))
    jd = jd[~((jd["capteur"] == "S-NPP") & (jd["annee"] == 2013))]
    tables.ecrire(jd, tables.chemin_table(tmp_path, "jours_disponibles"))
    conv = calibrer(cfg)
    assert np.isfinite(conv["se_stab"]).all() and (conv["se_stab"] > 0).all()
    fac = conv.groupby("jour_nuit")["facteur_viirs_vers_modis"].median()
    assert abs(fac["J"] - 1 / 4) < 0.03 and abs(fac["N"] - 1 / 12) < 0.015


def test_relais_noaa20_et_serie_multi_plateformes(tmp_path):
    """NOAA-20 (1,2 x S-NPP) raccordé sur 2018-2020 ; la série reste continue quand S-NPP disparaît."""
    from hexafire import tables
    from hexafire.harmonisation import calibrer, construire_serie
    from hexafire.occasions import passages_par_jour
    rng = np.random.default_rng(7)
    cfg = Config(tmp_path, tmp_path, tmp_path, tmp_path, 0.25, (0,), 30, ("l",), 2012, 2020, 2012, 2020, "2019-01")
    cells = np.unique(grille.cellule(rng.uniform(5, 12, 400), rng.uniform(0, 8, 400)))
    lat, _ = grille.centre(cells)
    caps = ("Terra", "Aqua", "S-NPP", "NOAA-20")
    pc = pd.concat([pd.DataFrame({"cellule": cells, "capteur": c, "n_jour": passages_par_jour(lat, c)}) for c in caps])
    actif = {"Terra": range(2012, 2023), "Aqua": range(2012, 2023), "S-NPP": range(2012, 2021), "NOAA-20": range(2018, 2023)}
    jd = pd.DataFrame([(c, a, m, 30, 30) for c in caps for a in actif[c] for m in (1, 2, 12)],
                      columns=["capteur", "annee", "mois", "jours_mois", "jours_disponibles"])
    tables.ecrire(pc, tables.chemin_table(tmp_path, "passages_cellule"))
    tables.ecrire(jd, tables.chemin_table(tmp_path, "jours_disponibles"))
    nj = {c: passages_par_jour(lat, c) for c in caps}
    fac = {"Terra": 1.0, "Aqua": 1.0, "S-NPP": 4.0, "NOAA-20": 4.8}
    lignes = []
    for a in range(2012, 2023):
        for m in (1, 2, 12):
            lam = rng.gamma(1.0, 0.05, len(cells))
            for cap in caps:
                if a not in actif[cap]:
                    continue
                n = rng.poisson(lam * nj[cap] * 30 * fac[cap])
                for c, k in zip(cells[n > 0], n[n > 0]):
                    lignes.append((c, a, m, cap, "J", k, 0.0))
    cm = pd.DataFrame(lignes, columns=["cellule", "annee", "mois", "capteur", "jour_nuit", "n", "frp_somme"])
    tables.ecrire(cm, tables.chemin_table(tmp_path, "cell_month"))
    calibrer(cfg)
    c20 = tables.lire(tables.chemin_table(tmp_path, "conversion_noaa20"))
    assert abs(c20["facteur_viirs_vers_modis"].median() - 1 / 4.8) < 0.02
    s = construire_serie(cfg)
    tot = s.groupby("annee")["N_harm"].sum()
    assert 0.85 < tot.loc[2021:2022].mean() / tot.loc[2012:2018].mean() < 1.15   # NOAA-20 seul après 2020
    assert "VIIRS (converti)" in set(s["source"])
