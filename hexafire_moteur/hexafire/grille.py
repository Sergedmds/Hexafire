# Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
"""Grille régulière en degrés : numérotation et centres des cellules.

Numérotation : cellule = ligne * n_lon + colonne, ligne 0 au nord (90° N),
colonne 0 à l'ouest (180° W). Une détection appartient à la cellule qui
contient son centre (règle P7). Les points situés exactement sur 180° E ou
90° S sont rangés dans la dernière colonne / ligne.
"""
from __future__ import annotations

import numpy as np


def cellule(lat, lon, pas: float = 0.25) -> np.ndarray:
    n_lon, n_lat = int(round(360 / pas)), int(round(180 / pas))
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")
    col = np.clip(np.floor((lon + 180.0) / pas).astype("int64"), 0, n_lon - 1)
    lig = np.clip(np.floor((90.0 - lat) / pas).astype("int64"), 0, n_lat - 1)
    return lig * n_lon + col


def centre(cell, pas: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    n_lon = int(round(360 / pas))
    cell = np.asarray(cell, dtype="int64")
    lig, col = np.divmod(cell, n_lon)
    lat = 90.0 - (lig + 0.5) * pas
    lon = -180.0 + (col + 0.5) * pas
    return lat, lon
