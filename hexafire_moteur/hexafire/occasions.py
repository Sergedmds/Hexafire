"""Étape 3 : occasions d'observation E (nombre de passages au-dessus d'une cellule).

Méthode de niveau 0 (analytique, utilisée pour le hackathon)
-----------------------------------------------------------
Les satellites sont sur des orbites héliosynchrones quasi polaires. Sur un mois,
le nombre moyen de passages au-dessus d'un point dépend surtout de sa latitude,
de la largeur de fauchée W et du nombre d'orbites par jour N :

    n(phi) = N * W / (2 pi R cos(phi) * |cos A(phi)|),   sin A = |cos i| / cos(phi)

où A est l'azimut de la trace au sol et i l'inclinaison de l'orbite. Le terme
|cos A| tient compte de l'obliquité de la trace près des hautes latitudes.
n est plafonné à N (on ne peut pas voir un point plus d'une fois par orbite).
Chaque jour compte un passage de jour et un passage de nuit.

    E(cellule, mois, capteur, période) = n(latitude du centre) * jours disponibles du capteur

Les jours disponibles sont déduits des données : un jour où le capteur détecte
moins de 10 % de son activité mondiale habituelle (médiane du mois) est considéré
comme manquant (panne, interruption). Si un fichier jours_manquants.csv
(colonnes : capteur, date AAAAMMJJ) est présent dans le dossier des agrégats,
ses jours sont ajoutés.

Cette méthode suppose une couverture uniforme en longitude sur un mois, ce qui
est raisonnable à l'échelle mensuelle. La méthode de niveau 1 (empreintes réelles
des passages issues du CMR de la NASA) pourra la remplacer sans changer la suite.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import grille, tables
from .config import Config

R_TERRE_KM = 6371.0

# largeur de fauchée (km), orbites par jour (1440 / période en minutes), inclinaison (degrés)
ORBITES = {
    "Terra":   {"fauchee": 2330.0, "orbites_jour": 1440 / 98.88, "inclinaison": 98.2},
    "Aqua":    {"fauchee": 2330.0, "orbites_jour": 1440 / 98.82, "inclinaison": 98.2},
    "S-NPP":   {"fauchee": 3060.0, "orbites_jour": 1440 / 101.44, "inclinaison": 98.7},
    "NOAA-20": {"fauchee": 3060.0, "orbites_jour": 1440 / 101.44, "inclinaison": 98.7},
    "NOAA-21": {"fauchee": 3060.0, "orbites_jour": 1440 / 101.44, "inclinaison": 98.7},
}
SEUIL_JOUR_MANQUANT = 0.10


def passages_par_jour(lat_deg, capteur: str) -> np.ndarray:
    """Nombre moyen de passages par jour et par période (jour ou nuit) à une latitude."""
    o = ORBITES[capteur]
    phi = np.radians(np.asarray(lat_deg, dtype="float64"))
    cos_phi = np.maximum(np.cos(phi), 1e-6)
    sin_a = np.minimum(abs(np.cos(np.radians(o["inclinaison"]))) / cos_phi, 1.0)
    cos_a = np.sqrt(np.maximum(1.0 - sin_a ** 2, 1e-6))
    n = o["orbites_jour"] * o["fauchee"] / (2 * np.pi * R_TERRE_KM * cos_phi * cos_a)
    return np.minimum(n, o["orbites_jour"])


def jours_disponibles(cfg: Config) -> pd.DataFrame:
    """Par capteur, période et mois : nombre de jours avec données."""
    cj = tables.lire(tables.chemin_table(cfg.agregats, "capteur_jour"))
    tot = cj.groupby(["capteur", "date"])["n"].sum().reset_index()
    tot["annee"], tot["mois"] = tot["date"] // 10000, tot["date"] // 100 % 100
    med = tot.groupby(["capteur", "annee", "mois"])["n"].transform("median")
    tot["disponible"] = tot["n"] >= SEUIL_JOUR_MANQUANT * med

    externe = cfg.agregats / "jours_manquants.csv"
    if externe.exists():
        jm = pd.read_csv(externe, dtype={"capteur": "string", "date": "int64"})
        cle = set(zip(jm["capteur"], jm["date"]))
        tot.loc[[(c, d) in cle for c, d in zip(tot["capteur"], tot["date"])], "disponible"] = False

    # Jours sans aucune ligne = jours sans données : on les compte à partir du calendrier
    lignes = []
    for (cap, an, mo), g in tot.groupby(["capteur", "annee", "mois"]):
        n_jours_mois = pd.Period(f"{an}-{mo:02d}").days_in_month
        lignes.append({"capteur": cap, "annee": an, "mois": mo,
                       "jours_mois": n_jours_mois, "jours_disponibles": int(g["disponible"].sum())})
    jd = pd.DataFrame(lignes)
    tables.ecrire(tot, tables.chemin_table(cfg.agregats, "jours_capteur"))
    return jd


def calculer(cfg: Config) -> None:
    """Écrit deux petites tables au lieu d'une table géante cellule x mois :

    - passages_cellule : (cellule, capteur, n_jour) = passages par jour et par période ;
    - jours_disponibles : (capteur, annee, mois, jours_mois, jours_disponibles).

    E s'obtient par produit au moment de l'usage : voir ajouter_occasions().
    """
    cm = tables.lire(tables.chemin_table(cfg.agregats, "cell_month"), colonnes=["cellule"])
    cellules = np.unique(cm["cellule"].to_numpy())  # cellules ayant connu au moins un feu
    lat, _ = grille.centre(cellules, cfg.pas)
    jd = jours_disponibles(cfg)
    pc = pd.concat([pd.DataFrame({"cellule": cellules, "capteur": cap,
                                  "n_jour": passages_par_jour(lat, cap).astype("float32")})
                    for cap in sorted(jd["capteur"].unique())], ignore_index=True)
    tables.ecrire(pc, tables.chemin_table(cfg.agregats, "passages_cellule"))
    tables.ecrire(jd, tables.chemin_table(cfg.agregats, "jours_disponibles"))
    print(f"occasions : {len(cellules):,} cellules actives, {len(jd)} capteur-mois -> {cfg.agregats}")
    manquants = jd[jd["jours_disponibles"] < jd["jours_mois"]]
    if len(manquants):
        print(f"  {len(manquants)} capteur-mois incomplets, par exemple :")
        print(manquants.head(8).to_string(index=False))


def ajouter_occasions(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Ajoute E et la couverture à une table qui a les colonnes cellule, capteur, annee, mois."""
    pc = tables.lire(tables.chemin_table(cfg.agregats, "passages_cellule"))
    jd = tables.lire(tables.chemin_table(cfg.agregats, "jours_disponibles"))
    out = (df.merge(pc, on=["cellule", "capteur"], how="left")
             .merge(jd, on=["capteur", "annee", "mois"], how="left"))
    out["E"] = out["n_jour"] * out["jours_disponibles"]
    out["couverture"] = out["jours_disponibles"] / out["jours_mois"]
    return out.drop(columns=["n_jour"])
