# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
"""Comptages par cellule, mois, capteur et période (jour/nuit).

Produit la table cell_month : une ligne par (cellule, annee, mois, capteur, jour_nuit)
avec le nombre de détections retenues et la somme de leur FRP. C'est l'entrée
du modèle de conversion (les occasions d'observation y seront jointes ensuite).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import tables
from .config import Config

CLES = ["cellule", "annee", "mois", "capteur", "jour_nuit"]


CLES_JOUR = ["capteur", "date", "jour_nuit"]


def agreger_fichier(chemin: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    det = tables.lire(chemin, colonnes=CLES + ["date", "frp"])
    cm = (det.groupby(CLES, sort=False)
             .agg(n=("frp", "size"), frp_somme=("frp", "sum"))
             .reset_index())
    # comptage mondial par jour : sert à repérer les jours sans données (voir occasions.py)
    jour = det.groupby(CLES_JOUR, sort=False).size().rename("n").reset_index()
    return cm, jour


def agreger_tout(cfg: Config) -> Path:
    fichiers = sorted(cfg.donnees_preparees.rglob(f"*{tables.EXT}"))
    # Un mois récupéré par l'API FIRMS (_api) est ignoré dès que l'archive mensuelle du même mois existe
    archives = {f.name.replace(tables.EXT, "") for f in fichiers if "_api" not in f.name}
    ignores = [f for f in fichiers if "_api" in f.name and f.name.replace("_api" + tables.EXT, "") in archives]
    fichiers = [f for f in fichiers if f not in ignores]
    if ignores:
        print(f"  {len(ignores)} mois API ignorés (archive disponible)")
    if not fichiers:
        raise SystemExit(f"Aucun fichier préparé dans {cfg.donnees_preparees}. Lancez d'abord : preparer")
    morceaux, jours = [], []
    for i, f in enumerate(fichiers, 1):
        cm_f, jour_f = agreger_fichier(f)
        morceaux.append(cm_f)
        jours.append(jour_f)
        if i % 25 == 0 or i == len(fichiers):
            print(f"  {i}/{len(fichiers)} fichiers agrégés")
    cm = (pd.concat(morceaux, ignore_index=True)
            .groupby(CLES, sort=True).sum().reset_index())
    cm["n"] = cm["n"].astype("int64")
    sortie = tables.ecrire(cm, tables.chemin_table(cfg.agregats, "cell_month"))
    cj = pd.concat(jours, ignore_index=True).groupby(CLES_JOUR, sort=True)["n"].sum().reset_index()
    tables.ecrire(cj, tables.chemin_table(cfg.agregats, "capteur_jour"))

    # Résumé lisible : total mensuel par capteur et période, pour un contrôle rapide
    resume = (cm.groupby(["capteur", "annee", "mois", "jour_nuit"])["n"].sum()
                .unstack("jour_nuit", fill_value=0).reset_index())
    resume.to_csv(cfg.agregats / "resume_mensuel.csv", index=False)
    print(f"cell_month : {len(cm):,} lignes, {int(cm['n'].sum()):,} détections -> {sortie}")
    return sortie
