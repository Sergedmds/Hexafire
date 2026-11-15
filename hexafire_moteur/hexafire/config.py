# Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
"""Chargement de la configuration (config.toml)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    donnees_brutes: Path
    donnees_preparees: Path
    agregats: Path
    journaux: Path
    pas: float
    types_conserves: tuple[int, ...]
    confiance_modis_min: int
    confiance_viirs_exclues: tuple[str, ...]
    debut_reference: int
    fin_reference: int
    debut_calibration: int
    fin_calibration: int
    bascule_viirs: str

    @property
    def n_lon(self) -> int:
        return int(round(360 / self.pas))

    @property
    def n_lat(self) -> int:
        return int(round(180 / self.pas))


def charger(chemin: str | Path | None = None) -> Config:
    chemin = Path(chemin) if chemin else RACINE / "config.toml"
    with open(chemin, "rb") as f:
        c = tomllib.load(f)
    base = chemin.resolve().parent

    def p(x: str) -> Path:
        q = Path(x)
        return q if q.is_absolute() else (base / q).resolve()

    ch, fi, pe = c["chemins"], c["filtres"], c["periodes"]
    return Config(
        donnees_brutes=p(ch["donnees_brutes"]),
        donnees_preparees=p(ch["donnees_preparees"]),
        agregats=p(ch["agregats"]),
        journaux=p(ch["journaux"]),
        pas=float(c["grille"]["pas_degres"]),
        types_conserves=tuple(fi["types_conserves"]),
        confiance_modis_min=int(fi["confiance_modis_min"]),
        confiance_viirs_exclues=tuple(s.lower() for s in fi["confiance_viirs_exclues"]),
        debut_reference=int(pe["debut_reference"]),
        fin_reference=int(pe["fin_reference"]),
        debut_calibration=int(pe["debut_calibration"]),
        fin_calibration=int(pe["fin_calibration"]),
        bascule_viirs=str(pe["bascule_viirs"]),
    )
