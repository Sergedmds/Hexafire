# Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hexafire import grille, tables
from hexafire.agregation import agreger_tout
from hexafire.config import Config
from hexafire.lecture import identifier, inventaire
from hexafire.preparation import filtrer, preparer_tout


def cfg_test(tmp: Path) -> Config:
    return Config(
        donnees_brutes=tmp / "brutes", donnees_preparees=tmp / "prep", agregats=tmp / "agr",
        journaux=tmp / "jx", pas=0.25, types_conserves=(0,), confiance_modis_min=30,
        confiance_viirs_exclues=("l",), debut_reference=2003, fin_reference=2020,
        debut_calibration=2012, fin_calibration=2020, bascule_viirs="2021-01",
    )


MODIS_TXT = """YYYYMMDD HHMM sat lat lon T21 T31 sample FRP conf type dn
20230101 0128 T -13.3373  -44.1169 303.3 292.5  362     7.0  54  0 N
20230101 0128 A -13.2674  -45.5538 320.0 291.2  491    20.0 100  0 D
20230101 0128 A  10.0000    2.0000 320.0 291.2  491    20.0  20  0 D
20230102 1301 T  19.4000 -155.2000 330.0 291.2  100    50.0  90  1 D
"""

VIIRS_CSV = ("YYYYMMDD,HHMM,Line,Sample,Lat,Lon,T4,T5,MeanT4,MeanT5,MeanDT,MADT4,MADT5,MADDT,FRP,Rad13,Mean13,"
             "AdjC,AdjW,WinS,Confidence,DNFlag,SZA,SAA,VZA,VAA,Glint,Type,PixArea\n"
             "20230101,0104,1,5635,9.9,2.1,322,252,0,0,0,0,0,0,2.03,0.1,0.1,8,0,0,N,D,114,83,59.2,-34,81,0,0.257\n"
             "20230101,0104,1,5635,9.9,2.1,322,252,0,0,0,0,0,0,2.03,0.1,0.1,8,0,0,L,D,114,83,59.2,-34,81,0,0.257\n"
             "20230101,0104,1,5635,9.9,2.1,322,252,0,0,0,0,0,0,2.03,0.1,0.1,8,0,0,H,N,114,83,59.2,-34,81,0,0.257\n"
             "20230101,0104,1,5635,9.9,2.1,322,252,0,0,0,0,0,0,2.03,0.1,0.1,8,0,0,N,N,114,83,59.2,-34,81,2,0.257\n")


def ecrire_gz(chemin: Path, texte: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(chemin, "wt") as f:
        f.write(texte)


def test_cellules_bords():
    c = grille.cellule([90, -90, 0, 0], [-180, 180, 0, -0.0001])
    assert c[0] == 0                         # coin nord-ouest
    assert c[1] == 720 * 1440 - 1            # coin sud-est (bornes incluses)
    lat, lon = grille.centre(c[2])
    assert lat == pytest.approx(-0.125) and lon == pytest.approx(0.125)


def test_identification_et_version(tmp_path):
    b = tmp_path / "brutes"
    for nom in ["MCD14ML.202301.006.03.txt.gz", "MCD14ML.202301.061.03.txt.gz",
                "MCD14ML.202212.006.03.txt.gz", "VNP14IMGML.201901.C2.03.csv.gz",
                "VNP14IMGML.201901.C2.04.csv.gz", "journal.txt"]:
        ecrire_gz(b / nom, "x")
    arch = {(a.produit, a.annee, a.mois): a for a in inventaire(b)}
    assert arch[("MCD14ML", 2023, 1)].collection == "061"
    assert arch[("MCD14ML", 2022, 12)].collection == "006"
    assert arch[("VNP14IMGML", 2019, 1)].version == 4
    assert identifier(b / "journal.txt") is None


def test_preparation_et_conservation(tmp_path):
    cfg = cfg_test(tmp_path)
    ecrire_gz(cfg.donnees_brutes / "MCD14ML" / "MCD14ML.202301.061.03.txt.gz", MODIS_TXT)
    ecrire_gz(cfg.donnees_brutes / "VNP14IMGML" / "VNP14IMGML.202301.C2.04.csv.gz", VIIRS_CSV)
    faits = preparer_tout(cfg)
    assert len(faits) == 2
    eff = {r["produit"]: r["effectifs"] for r in faits}
    # MODIS : 1 volcan (type 1) exclu, 1 confiance 20 exclue -> 2 retenues
    assert eff["MCD14ML"] == {"lues": 4, "coord_invalides": 0, "type_exclu": 1, "confiance_exclue": 1,
                              "jour_nuit_inconnu": 0, "retenues": 2, "hors_mois": 0}
    # VIIRS : classe L exclue, type 2 exclu -> 2 retenues
    assert eff["VNP14IMGML"]["retenues"] == 2
    # Relancer ne refait rien
    assert preparer_tout(cfg) == []
    agreger_tout(cfg)
    cm = tables.lire(tables.chemin_table(cfg.agregats, "cell_month"))
    assert int(cm["n"].sum()) == 4
    assert set(cm["capteur"]) == {"Terra", "Aqua", "S-NPP"}
    snpp = cm[cm["capteur"] == "S-NPP"].set_index("jour_nuit")["n"]
    assert snpp["J"] == 1 and snpp["N"] == 1


def test_passages_par_jour():
    from hexafire.occasions import passages_par_jour
    eq_modis = float(passages_par_jour(0.0, "Aqua"))
    eq_viirs = float(passages_par_jour(0.0, "S-NPP"))
    # A l'équateur : MODIS ne voit pas chaque point chaque jour (trous entre orbites), VIIRS si
    assert 0.8 < eq_modis < 0.9
    assert 1.0 < eq_viirs < 1.15
    assert 1.2 < eq_viirs / eq_modis < 1.35
    # La couverture augmente avec la latitude et reste plafonnée
    assert float(passages_par_jour(60.0, "Aqua")) > 1.6
    assert float(passages_par_jour(85.0, "Aqua")) <= 1440 / 98.82
