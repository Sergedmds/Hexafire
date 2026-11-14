import numpy as np
import pandas as pd

from hexafire import grille, tables
from hexafire.config import Config
from hexafire.occasions import passages_par_jour
from hexafire.validation import kappa_cohen, valider


def test_kappa():
    a = np.array(["bas", "normal", "haut", "normal"])
    assert kappa_cohen(a, a) == 1.0
    assert kappa_cohen(a, np.array(["haut"] * 4)) <= 0.0


def test_validation_sur_donnees_simulees(tmp_path):
    rng = np.random.default_rng(5)
    cfg = Config(tmp_path, tmp_path, tmp_path, tmp_path, 0.25, (0,), 30, ("l",), 2003, 2020, 2012, 2020, "2021-01")
    cells = np.unique(grille.cellule(rng.uniform(5, 15, 600), rng.uniform(-5, 15, 600)))
    lat, _ = grille.centre(cells)
    caps = ("Terra", "Aqua", "S-NPP")
    jd = pd.DataFrame([(c, a, m, 30, 30) for c in caps for a in range(2003, 2016) for m in (1, 2, 12)
                       if not (c == "S-NPP" and a < 2012)],
                      columns=["capteur", "annee", "mois", "jours_mois", "jours_disponibles"])
    pc = pd.concat([pd.DataFrame({"cellule": cells, "capteur": c, "n_jour": passages_par_jour(lat, c)}) for c in caps])
    tables.ecrire(pc, tables.chemin_table(tmp_path, "passages_cellule"))
    tables.ecrire(jd, tables.chemin_table(tmp_path, "jours_disponibles"))
    nj = {c: passages_par_jour(lat, c) for c in caps}
    lignes = []
    for a in range(2003, 2016):
        for m in (1, 2, 12):
            annee_fac = rng.lognormal(0, 0.5)            # années plus ou moins actives -> verdicts variés
            lam = rng.gamma(1.0, 0.03, len(cells)) * annee_fac
            for d, fac in (("J", 5.0), ("N", 15.0)):
                for cap, f in (("Terra", 1.0), ("Aqua", 1.0), ("S-NPP", fac)):
                    if cap == "S-NPP" and a < 2012:
                        continue
                    n = rng.poisson(lam * nj[cap] * 30 * f)
                    for c, k in zip(cells[n > 0], n[n > 0]):
                        lignes.append((c, a, m, cap, d, k, 0.0))
    cm = pd.DataFrame(lignes, columns=["cellule", "annee", "mois", "capteur", "jour_nuit", "n", "frp_somme"])
    tables.ecrire(cm, tables.chemin_table(tmp_path, "cell_month"))
    res = valider(cfg).set_index("methode")
    assert res.loc["HEXAFIRE", "kappa"] > 0.6
    assert abs(res.loc["HEXAFIRE", "biais_median"]) < 0.10
    assert res.loc["M0 raccord brut", "kappa"] < 0.2      # sans conversion, tout paraît « haut »


def test_publication_exemple(tmp_path):
    import json
    from hexafire.publication import publier_exemple
    publier_exemple(tmp_path / "donnees")
    idx = json.loads((tmp_path / "donnees" / "index.json").read_text())
    assert idx["format"] == 2 and idx["mois"][0]["t"] == 0 and idx["tuiles"] and "viirs" in idx["unites"]
    t = json.loads((tmp_path / "donnees" / "tuiles" / f"t_{idx['tuiles'][0]}.json").read_text())
    assert len(t["cellules"]) == len(t["t"]) == len(t["v"]) == len(t["w"]) == len(t["e"]) == len(t["f"]) > 0
    assert idx["taille_bloc"] == 10.0 and len(t["p"]) == len(t["v"])
    # couche de la carte : un fichier par mois observé, rapports calculés pour les cellules actives
    dernier = idx["mois"][-1]["t"]
    c = json.loads((tmp_path / "donnees" / "cartes" / f"m_{dernier}.json").read_text())
    assert len(c["c"]) == len(c["v"]) == len(c["r"]) == len(c["w"]) > 0
    assert any(r > 0 for r in c["r"]) and all(r == -1 or r >= 0 for r in c["r"])
