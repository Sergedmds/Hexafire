"""Point d'entrée du moteur HEXAFIRE.

    python -m hexafire inventaire         # ce qui est téléchargé et sera utilisé
    python -m hexafire preparer           # filtre et range les détections (relançable)
    python -m hexafire preparer --produits MCD14ML --limite 3
    python -m hexafire agreger            # comptages cellule x mois x capteur x jour/nuit
    python -m hexafire occasions          # passages par cellule et jours disponibles
    python -m hexafire calibrer           # facteurs de conversion S-NPP -> MODIS (2012-2020)
    python -m hexafire serie              # série harmonisée en équivalent MODIS
    python -m hexafire valider            # tests T1, T2, T4 (une année exclue) et comparaison M0, M1
    python -m hexafire firms              # mois récents via l'API FIRMS (export FIRMS_MAP_KEY=...)
    python -m hexafire publier            # fichiers de l'application web (../hexafire_web/donnees)
    python -m hexafire publier --exemple  # jeu fictif au même format, pour développer l'interface
"""
from __future__ import annotations

import argparse
from collections import Counter

from . import agregation, firms_recent, harmonisation, occasions, preparation, publication, validation
from .config import RACINE
from .config import charger
from .lecture import inventaire


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="hexafire", description="Moteur d'harmonisation HEXAFIRE")
    ap.add_argument("--config", default=None, help="chemin de config.toml")
    sub = ap.add_subparsers(dest="commande", required=True)
    sub.add_parser("inventaire")
    p = sub.add_parser("preparer")
    p.add_argument("--produits", nargs="*", choices=["MCD14ML", "VNP14IMGML", "VJ114IMGML", "VJ214IMGML"])
    p.add_argument("--limite", type=int, default=None, help="nombre maximal d'archives à traiter")
    p.add_argument("--forcer", action="store_true", help="refaire même si déjà préparé")
    sub.add_parser("agreger")
    sub.add_parser("occasions")
    c = sub.add_parser("calibrer")
    c.add_argument("--bloc", type=float, default=10.0, help="taille des strates en degrés (défaut 10)")
    sr = sub.add_parser("serie")
    sr.add_argument("--bloc", type=float, default=10.0)
    fi = sub.add_parser("firms", help="mois récents via l'API FIRMS (clé : FIRMS_MAP_KEY ou --cle)")
    fi.add_argument("--cle", default=None)
    fi.add_argument("--seulement-preparer", action="store_true", help="ne rien télécharger, préparer les CSV déjà là")
    pu = sub.add_parser("publier")
    pu.add_argument("--exemple", action="store_true", help="jeu fictif pour développer l'application")
    pu.add_argument("--dossier", default=None, help="défaut : ../hexafire_web/donnees")
    pu.add_argument("--bloc", type=float, default=10.0, help="taille des strates (comme calibrer)")
    va = sub.add_parser("valider")
    va.add_argument("--bloc", type=float, default=10.0)
    a = ap.parse_args(argv)
    cfg = charger(a.config)

    if a.commande == "inventaire":
        arch = inventaire(cfg.donnees_brutes)
        c = Counter(x.produit for x in arch)
        print(f"Dossier : {cfg.donnees_brutes}")
        for prod in sorted(c):
            mois = sorted((x.annee, x.mois) for x in arch if x.produit == prod)
            print(f"  {prod:<11} {c[prod]:>4} mois  ({mois[0][0]}-{mois[0][1]:02d} -> {mois[-1][0]}-{mois[-1][1]:02d})")
    elif a.commande == "preparer":
        faits = preparation.preparer_tout(cfg, a.produits, a.limite, a.forcer)
        print(f"{len(faits)} archive(s) préparée(s). Journal : {cfg.journaux / 'preparation.jsonl'}")
    elif a.commande == "agreger":
        agregation.agreger_tout(cfg)
    elif a.commande == "occasions":
        occasions.calculer(cfg)
    elif a.commande == "calibrer":
        harmonisation.calibrer(cfg, a.bloc)
    elif a.commande == "serie":
        harmonisation.construire_serie(cfg, a.bloc)
    elif a.commande == "firms":
        if a.seulement_preparer:
            firms_recent.preparer_api(cfg)
        else:
            firms_recent.executer(cfg, a.cle)
    elif a.commande == "publier":
        from pathlib import Path
        dossier = Path(a.dossier) if a.dossier else (RACINE.parent / "hexafire_web" / "donnees")
        if a.exemple:
            publication.publier_exemple(dossier)
        else:
            publication.publier(cfg, dossier, a.bloc)
    elif a.commande == "valider":
        validation.valider(cfg, a.bloc)


if __name__ == "__main__":
    main()
