# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
"""Lecture et écriture des tables intermédiaires.

Format de référence : Parquet (pyarrow). Si pyarrow n'est pas installé,
repli automatique sur CSV compressé, pour que la chaîne reste testable.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import pyarrow  # noqa: F401
    PARQUET = True
except ImportError:  # pragma: no cover - dépend de l'environnement
    PARQUET = False

EXT = ".parquet" if PARQUET else ".csv.gz"


def chemin_table(dossier: Path, nom: str) -> Path:
    return Path(dossier) / f"{nom}{EXT}"


def ecrire(df: pd.DataFrame, chemin: Path) -> Path:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_name(chemin.name + ".tmp")
    if PARQUET:
        df.to_parquet(tmp, index=False, compression="zstd")
    else:
        df.to_csv(tmp, index=False, compression="gzip")
    tmp.replace(chemin)  # écriture atomique : pas de fichier à moitié écrit
    return chemin


def lire(chemin: Path, colonnes: list[str] | None = None) -> pd.DataFrame:
    chemin = Path(chemin)
    if chemin.suffix == ".parquet":
        return pd.read_parquet(chemin, columns=colonnes)
    return pd.read_csv(chemin, usecols=colonnes, parse_dates=False)
