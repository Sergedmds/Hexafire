# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
"""Lecture des archives mensuelles MCD14ML (MODIS) et Vxx14IMGML (VIIRS).

Toutes les détections sont ramenées à un schéma commun :

    capteur     'Terra', 'Aqua', 'S-NPP', 'NOAA-20', 'NOAA-21'
    famille     'MODIS' ou 'VIIRS'
    date        AAAAMMJJ (entier)          hhmm   heure UTC (entier, 236 = 02 h 36)
    annee, mois
    lat, lon    degrés                      frp    MW
    conf        confiance brute (MODIS : 0-100 en texte ; VIIRS : 'l', 'n', 'h')
    jour_nuit   'J' ou 'N'                  type   0 végétation, 1 volcan, 2 source fixe, 3 en mer
    sample      position dans le balayage   vza    angle de visée (VIIRS seulement)
    pixarea     surface du pixel en km² (VIIRS seulement)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

MOTIF = re.compile(
    r"^(?P<produit>MCD14ML|VNP14IMGML|VJ114IMGML|VJ214IMGML)\."
    r"(?P<ym>\d{6})\.(?P<coll>[0-9A-Z]+)\.(?P<ver>\d+)\.(?:txt|csv)\.gz$"
)
CAPTEUR_VIIRS = {"VNP14IMGML": "S-NPP", "VJ114IMGML": "NOAA-20", "VJ214IMGML": "NOAA-21"}
CAPTEUR_MODIS = {"T": "Terra", "A": "Aqua"}


@dataclass(frozen=True)
class Archive:
    chemin: Path
    produit: str
    annee: int
    mois: int
    collection: str
    version: int

    @property
    def famille(self) -> str:
        return "MODIS" if self.produit == "MCD14ML" else "VIIRS"

    @property
    def cle(self) -> tuple[str, int, int]:
        return (self.produit, self.annee, self.mois)


def identifier(chemin: Path) -> Archive | None:
    m = MOTIF.match(Path(chemin).name)
    if not m:
        return None
    ym = m["ym"]
    return Archive(Path(chemin), m["produit"], int(ym[:4]), int(ym[4:]), m["coll"], int(m["ver"]))


def inventaire(dossier: Path) -> list[Archive]:
    """Liste les archives et garde une seule version par produit et par mois.

    MODIS : collection 6 (006) jusqu'en décembre 2022, collection 6.1 (061) ensuite.
    VIIRS : version la plus élevée. Un même fichier présent dans deux dossiers
    (cas du fichier NOAA-20 rangé dans le dossier S-NPP) n'est gardé qu'une fois.
    """
    candidats: dict[tuple, list[Archive]] = {}
    for f in sorted(Path(dossier).rglob("*.gz")):
        a = identifier(f)
        if a:
            candidats.setdefault(a.cle, []).append(a)

    retenues = []
    for cle, liste in sorted(candidats.items()):
        produit, annee, _ = cle
        if produit == "MCD14ML":
            voulue = "006" if annee <= 2022 else "061"
            ok = [a for a in liste if a.collection == voulue] or liste
        else:
            ok = liste
        retenues.append(max(ok, key=lambda a: (a.version, a.chemin.name)))
    return retenues


def _lire_modis(chemin: Path) -> pd.DataFrame:
    df = pd.read_csv(chemin, sep=r"\s+", dtype={"YYYYMMDD": "int64", "HHMM": "int64", "sat": "string",
                                                 "conf": "string", "dn": "string"})
    if "dn" not in df.columns:  # version 1 du produit : pas de colonne jour/nuit
        df["dn"] = pd.NA
    out = pd.DataFrame({
        "capteur": df["sat"].map(CAPTEUR_MODIS),
        "famille": "MODIS",
        "date": df["YYYYMMDD"].astype("int64"),
        "hhmm": df["HHMM"].astype("int64"),
        "lat": df["lat"].astype("float64"),
        "lon": df["lon"].astype("float64"),
        "frp": df["FRP"].astype("float64"),
        "conf": df["conf"].astype("string"),
        "jour_nuit": df["dn"].astype("string").str.upper().map({"D": "J", "N": "N"}),
        "type": df["type"].astype("int64"),
        "sample": df["sample"].astype("float64"),
        "vza": np.nan,
        "pixarea": np.nan,
    })
    return out


COLONNES_VIIRS = ["YYYYMMDD", "HHMM", "Sample", "Lat", "Lon", "FRP", "Confidence",
                  "DNFlag", "VZA", "Type", "PixArea"]


def _lire_viirs(chemin: Path, capteur: str) -> pd.DataFrame:
    df = pd.read_csv(chemin, usecols=COLONNES_VIIRS,
                     dtype={"YYYYMMDD": "int64", "HHMM": "int64", "Confidence": "string", "DNFlag": "string"})
    out = pd.DataFrame({
        "capteur": capteur,
        "famille": "VIIRS",
        "date": df["YYYYMMDD"],
        "hhmm": df["HHMM"],
        "lat": df["Lat"].astype("float64"),
        "lon": df["Lon"].astype("float64"),
        "frp": df["FRP"].astype("float64"),
        "conf": df["Confidence"].str.strip().str.lower(),
        "jour_nuit": df["DNFlag"].str.strip().str.upper().map({"D": "J", "N": "N"}),
        "type": df["Type"].astype("int64"),
        "sample": df["Sample"].astype("float64"),
        "vza": df["VZA"].astype("float64"),
        "pixarea": df["PixArea"].astype("float64"),
    })
    return out


def lire_archive(a: Archive) -> pd.DataFrame:
    if a.famille == "MODIS":
        df = _lire_modis(a.chemin)
    else:
        df = _lire_viirs(a.chemin, CAPTEUR_VIIRS[a.produit])
    df["annee"] = (df["date"] // 10000).astype("int64")
    df["mois"] = (df["date"] // 100 % 100).astype("int64")
    return df
