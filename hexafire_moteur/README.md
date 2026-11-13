# HEXAFIRE — moteur d'harmonisation (v0.1)

Chaîne hors ligne qui transforme les archives FIRMS/UMD en comptages harmonisés.

| Étape | Module | État |
|---|---|---|
| 1. Acquisition | `../telecharger_archives.sh` | fait |
| 2. Préparation (règles P1–P9) | `hexafire/preparation.py` | **fait** |
| 2b. Comptages cellule × mois | `hexafire/agregation.py` | **fait** |
| 3. Occasions d'observation (niveau 0 analytique ; CMR plus tard) | `hexafire/occasions.py` | **fait** |
| 4a. Conversion S-NPP → MODIS (strates de 10°, jour/nuit) | `hexafire/harmonisation.py` | **fait** |
| 4b. Série harmonisée + poids + statuts (S-NPP) | `hexafire/harmonisation.py` | **fait** |
| 4c. Relais NOAA-20 / NOAA-21 (raccordés à S-NPP), série multi-plateformes | `hexafire/harmonisation.py` | **fait** |
| 4d. Mois récents via l'API FIRMS (SP sinon NRT) | `hexafire/firms_recent.py` | **fait** |
| 4e. Incertitude des valeurs converties (tirages) | — | à faire |
| 5. Validation T1, T2, T4 (une année exclue) + comparaison M0, M1 | `hexafire/validation.py` | **fait** |
| 6. Publication pour l'application web (format v1, tuiles de 5°) | `hexafire/publication.py` | **fait** |

## Installation (une seule fois)

```bash
cd ~/Documents/Hackathon_NASA_2026/hexafire_moteur
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q          # 14 tests doivent passer
```

## Utilisation

```bash
source .venv/bin/activate
python -m hexafire inventaire   # ce qui est téléchargé et sera utilisé
python -m hexafire preparer     # relançable à volonté pendant les téléchargements
python -m hexafire agreger      # produit ../agregats/cell_month.parquet, capteur_jour.parquet, resume_mensuel.csv
python -m hexafire occasions    # passages par cellule + jours disponibles par capteur et par mois
python -m hexafire calibrer     # facteurs S-NPP -> MODIS (agregats/conversion_snpp.parquet)
python -m hexafire valider      # résultats dans ../journaux/validation_resultats.csv
export FIRMS_MAP_KEY=votre_cle && python -m hexafire firms   # mois récents (API FIRMS)
python -m hexafire publier      # fichiers de l'application -> ../hexafire_web/donnees (--exemple : jeu fictif)
                                # format v2 : tuiles (équiv. MODIS v, équiv. VIIRS w, brut b) + cartes mensuelles de 1°
python -m hexafire serie        # série harmonisée (agregats/harmonized_cell_month.parquet, serie_mois.parquet)
```

Options utiles : `python -m hexafire preparer --produits MCD14ML --limite 5`.

## Où vont les fichiers

```
Hackathon_NASA_2026/
├── donnees_brutes/        archives téléchargées (ne pas modifier)
├── donnees_preparees/     détections filtrées : <capteur>/<année>/<capteur>_<AAAAMM>.parquet
├── agregats/              cell_month.parquet, resume_mensuel.csv
├── journaux/              preparation.jsonl (empreinte SHA-256, effectifs avant/après filtres)
└── hexafire_moteur/       ce code
```

## Règles appliquées

- MODIS : collection 6 jusqu'en décembre 2022, 6.1 ensuite ; VIIRS : version la plus récente.
- Conservés : type 0 (feu de végétation), confiance MODIS ≥ 30, VIIRS hors classe « faible ».
- Cellule de 0,25° contenant le centre de la détection ; jour et nuit gardés séparément.
- Contrôle automatique : lues = retenues + exclues (par motif), sinon arrêt.
