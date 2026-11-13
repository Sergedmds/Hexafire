# HEXAFIRE — Harmonized MODIS + VIIRS hotspot calendar, 2000 → today

**NASA Space Apps Challenge 2026 — challenge “Harmonization of MODIS and VIIRS Hot Spots”**
Team HEXAFIRE (ENSGMM / UNSTIM, Benin)

🔗 **Live app:** `https://<github-user>.github.io/<repo>/` · 📘 User guide (FR): [`hexafire_web/docs/GUIDE_UTILISATEUR.pdf`](hexafire_web/docs/GUIDE_UTILISATEUR.pdf)

## The problem

NASA has mapped active fires from space with **MODIS** (Terra, Aqua) since 2000 and with **VIIRS** (Suomi NPP, NOAA-20,
NOAA-21) since 2012. VIIRS pixels are smaller (375 m vs 1 km), so VIIRS detects **about 5× more hotspots by day and
15× more by night**. As MODIS is retired, any long-term analysis that switches from MODIS to VIIRS shows a **false jump**
in fire activity. Fire managers, early-warning services and scientists cannot compare a recent season with 20 years of
history.

## Our solution

1. **Harmonization engine** (`hexafire_moteur/`, Python). It learns the VIIRS → MODIS conversion over 2012–2020, when
   both sensors observed together:
   - a conditional binomial model with an observation-opportunity offset (number of satellite overpasses);
   - fitted by **region × month of year × day/night**, then stabilized by shrinkage;
   - NOAA-20 and NOAA-21 are chained to S-NPP.

   The result is **one consistent monthly series per 0.25° cell from November 2000 to today**, expressed in MODIS
   equivalent (or VIIRS equivalent).
2. **Web app** (`hexafire_web/`, static HTML/JS, layout inspired by NASA POWER). Draw any area in the world (point +
   radius, box, polygon, country) and get:
   - a **year × month calendar** of hotspots, or of **departure from the 2003–2020 normal** (colour-blind-safe palette);
   - seasonal analyses;
   - the sensor-change proof;
   - a monthly world map;
   - CSV / JSON / PNG / SVG downloads and a shareable link.

   Available in French and English, with light and dark themes.

## Does it work? Leave-one-year-out validation

For each test year, the conversion is fitted without that year. VIIRS is converted as if MODIS no longer existed, and
the monthly verdict (low / normal / high) is compared with real MODIS. Results on 2012–2015, over 7,604 region-months:

| Method | Kappa (≥ 0.5) | False anomalies (≤ 0.15) | Median bias (\|·\| < 0.10) | Median error (< 0.25) | Max yearly step (< 0.10) |
|---|---|---|---|---|---|
| **HEXAFIRE** | **0.735** ✓ | **0.098** ✓ | **0.014** ✓ | **0.127** ✓ | **0.051** ✓ |
| M1: one global factor | 0.553 ✓ | 0.239 ✗ | 0.045 ✓ | 0.255 ✗ | 0.123 ✗ |
| M0: raw VIIRS | 0.015 ✗ | 0.925 ✗ | 1.962 ✗ | 1.962 ✗ | 2.028 ✗ |

HEXAFIRE beats the single-factor approach: the 95% bootstrap interval of kappa(HEXAFIRE) − kappa(M1) is
[0.168 ; 0.195], entirely above 0. *Validation will be extended to 2012–2020 once all VIIRS archives are processed.*

## Documentation (French)

| Document | Content |
|---|---|
| [`hexafire_web/docs/DOSSIER_TECHNIQUE.pdf`](hexafire_web/docs/DOSSIER_TECHNIQUE.pdf) | Full technical dossier: architecture, dependencies, mathematical models, data formats, results |
| [`hexafire_moteur/GUIDE_EXECUTION.md`](hexafire_moteur/GUIDE_EXECUTION.md) | Running the engine step by step, and how to read its outputs |
| [`hexafire_web/docs/GUIDE_UTILISATEUR.pdf`](hexafire_web/docs/GUIDE_UTILISATEUR.pdf) | Illustrated user guide of the web app |
| [`hexafire_web/FICHE_TECHNIQUE.pdf`](hexafire_web/FICHE_TECHNIQUE.pdf) | Web app technical sheet |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | Data provenance and terms of use (English) |

## Repository layout

| Path | Content |
|---|---|
| `hexafire_moteur/` | Harmonization engine (Python 3.12): download prep, aggregation, overpasses, calibration, validation, series, publication. Run guide: `GUIDE_EXECUTION.md` (FR) |
| `hexafire_web/` | Static web app; `FICHE_TECHNIQUE.pdf` (technical sheet), `docs/GUIDE_UTILISATEUR.pdf` (user guide) |
| `telecharger_archives.sh` | Download of the MODIS/VIIRS monthly archives (UMD SFTP mirror of NASA FIRMS) |
| `HEXAFIRE_v2_fusion.tex` | Research document (methods, state of the art, design) |
| `publier_site.sh` | Deploys the app and its data to GitHub Pages (`gh-pages` branch) |

Large data folders (`donnees_brutes/`, `donnees_preparees/`, `agregats/`, `journaux/`, `hexafire_web/donnees/`) are not
versioned. They are rebuilt by the engine.

## Quick start

```bash
cd hexafire_moteur
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt   # Python >= 3.11
pytest -q                                   # 14 tests
python -m hexafire publier --exemple        # fictitious dataset, to try the app
cd ../hexafire_web && python3 -m http.server 8000   # open http://localhost:8000
```

Full pipeline on real data: `inventaire → preparer → (firms) → agreger → occasions → calibrer → valider → serie → publier`
(see `hexafire_moteur/GUIDE_EXECUTION.md`).

## NASA data used

- **MODIS** active fires: MCD14ML monthly archives, collections 6 (2000–2022) and 6.1 (2023 →).
- **VIIRS** 375 m active fires: VNP14IMGML (S-NPP), VJ114IMGML (NOAA-20), VJ214IMGML (NOAA-21), collection 2.
- **NASA FIRMS** API for the most recent months (NRT / standard products).

The monthly archives were downloaded from the University of Maryland fire team server (`fuoco.geog.umd.edu`, a
non-U.S. Government site that hosts the NASA products). **Full provenance, versions, retrieval dates and terms of use:
[`DATA_SOURCES.md`](DATA_SOURCES.md).**

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS)
> (https://www.earthdata.nasa.gov/firms), part of NASA's Earth Science Data and Information System (ESDIS).

References: Giglio et al. (2016), *Remote Sensing of Environment* 178:31–41; Schroeder et al. (2014), *Remote Sensing of
Environment* 143:85–96. Basemap and place search: © OpenStreetMap contributors (ODbL). Country borders: Natural Earth
(public domain). NASA does not endorse this project; data are provided “as is”.

## Limits

- A hotspot is not a wildfire, and the absence of hotspots does not prove the absence of fire.
- Overpasses are computed analytically (level 0). Strata are 10° blocks; GFED regions × land cover are planned.
- Values for converted months carry a conversion uncertainty that is not yet displayed.

## Use of AI tools

AI tools were used during development, as required by the Space Apps rules. A full description will be provided in
the project submission.

## Team

HEXAFIRE — ENSGMM / UNSTIM (Abomey, Benin).
