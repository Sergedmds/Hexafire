# HEXAFIRE

**A harmonized MODIS and VIIRS hotspot calendar, from November 2000 to today**

NASA Space Apps Challenge 2026, challenge *Harmonization of MODIS and VIIRS Hot Spots*.
Team HEXAFIRE, ENSGMM, Université Nationale des Sciences, Technologies, Ingénierie et Mathématiques (UNSTIM), Abomey, Benin.

| | |
|---|---|
| **Web application** | <https://sergedmds.github.io/Hexafire/> |
| **Research document** | [English](HEXAFIRE_document_en.pdf) · [Français](HEXAFIRE_document.pdf) |
| **Data provenance** | [`DATA_SOURCES.md`](DATA_SOURCES.md) |

---

## The problem

NASA has mapped active fires from space with MODIS (Terra and Aqua) since 2000, and with VIIRS (Suomi NPP, NOAA-20,
NOAA-21) since 2012. VIIRS pixels are smaller (375 m against 1 km), so for the same number of overpasses VIIRS detects
about 5 times more hotspots than MODIS by day and 15 times more at night.

MODIS is now reaching the end of its life. Any long record that switches from MODIS to VIIRS shows a rise in fire
activity that never happened. A fire manager comparing this season with twenty years of history cannot tell a severe
season from a more sensitive satellite.

## Our approach

HEXAFIRE expresses VIIRS detections in MODIS units, using the years 2012–2020 when both sensors flew together.

1. **Same number of looks.** For each 0.25° cell, the engine computes how many times each satellite passed over it
   in a month, from orbital geometry and the days with data.
2. **A conversion that ignores the fires themselves.** For a cell-month seen by both sensors, the VIIRS share of the
   combined count depends only on the sensitivity gap and on the overpass ratio. The true fire activity cancels out.
   The gap is estimated by maximum likelihood for each 10° block, calendar month and period (day or night), and
   estimates from sparse blocks are pulled towards their block average.
3. **One series.** Terra and Aqua are kept as measured until December 2020. Converted VIIRS takes over in January
   2021, before the orbital drift of Terra and Aqua. NOAA-20 and NOAA-21 are linked to Suomi NPP, and several VIIRS
   satellites are averaged, never added.
4. **Honest labels.** Every month carries an observation status (measured, converted, provisional, partial coverage)
   and every converted value carries a 95% conversion interval.

The full model, with its equations, is described in the research document.

## Validation

The challenge asks that the sensor of origin no longer matter. We test exactly that.

For each year from 2012 to 2020, the conversion is fitted without that year. Suomi NPP is then converted as if MODIS
no longer existed, and each region-month gets a verdict (low, normal or high, against the 2003–2011 MODIS
percentiles). This verdict is compared with the one given by real MODIS, over 17,309 region-months.

| Method | Cohen's κ | False anomalies | Median bias | Median error | Largest annual error |
|---|---|---|---|---|---|
| **HEXAFIRE** | **0.747** | **9.0%** | **0.007** | **0.125** | **0.049** |
| One global factor (same overpass correction, day and night) | 0.558 | 23.9% | 0.032 | 0.262 | 0.117 |
| Raw VIIRS | 0.014 | 92.1% | 1.955 | 1.955 | 2.028 |
| Target | ≥ 0.5 | ≤ 15% | below 0.10 | < 0.25 | < 0.10 |

Errors are differences of log(1 + count). The 95% interval of κ(HEXAFIRE) − κ(global factor), obtained by
resampling the nine test years, is [0.174, 0.205].

The global factor already uses the overpass correction and the day/night split, so the gain comes from the
region- and month-specific conversion. The separate contribution of each component has not yet been measured.

## The web application

A static site: no server, no account, no installation. It runs on a computer or a phone, in English or French.

- **Choose an area.** Draw a rectangle or a polygon, set a point and a radius, pick a country or search for a place.
- **Calendar.** A year × month grid of harmonized hotspots, or of the departure from the 2003–2020 median, with
  colour-blind-safe palettes. Four indicators sit above it: the latest month available, its departure from normal,
  its rank among past years, and the usual peak month of the area. Hovering a month shows its value, its 95%
  conversion interval, the raw detections, the median of that month and the mean fire radiative power (FRP).
- **Analyses.** Seasonal profile, cumulative season against past seasons, ranking of years, most unusual months.
- **Sensors.** The raw record and the harmonized record side by side: the jump at the sensor change disappears,
  year-to-year variation stays. Converted months are shown with their uncertainty band, next to the validation table.
- **Map of the month.** Harmonized hotspots or departure from normal on a 1° world grid, with a month slider.
- **Downloads.** Calendar (CSV, JSON, PNG, SVG), cell × month table of the area (CSV) and a shareable link.

Values can be shown in MODIS-equivalent or VIIRS-equivalent units. The departure from normal is practically the same
in both.

## Data

| Data | Version | Period used |
|---|---|---|
| MODIS active fire monthly archives, MCD14ML (Terra, Aqua, 1 km) | C6 006.03, then C6.1 061.03 | Nov 2000 – Aug 2026 |
| VIIRS 375 m active fire monthly archives, VNP14IMGML (Suomi NPP) | Collection 2 | Jan 2012 – Jul 2026 |
| VIIRS 375 m, VJ114IMGML (NOAA-20) and VJ214IMGML (NOAA-21) | Collection 2 | Apr 2018 / Mar 2023 – Jul 2026 |
| NASA FIRMS API | NRT and standard products | Months after the latest archive |

The monthly archives are the NASA products published by the NASA fire science team on the University of Maryland
server. Versions, retrieval dates and terms of use are listed in [`DATA_SOURCES.md`](DATA_SOURCES.md).

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS)
> (https://www.earthdata.nasa.gov/firms), part of NASA's Earth Science Data and Information System (ESDIS).

Basemap and place search: © OpenStreetMap contributors (ODbL). Country borders: Natural Earth (public domain).
Map rendering: MapLibre GL JS (BSD-3-Clause). NASA does not endorse this project.

## Repository

| Path | Content |
|---|---|
| `hexafire_moteur/` | Harmonization engine (Python 3.12): preparation, aggregation, overpasses, calibration, validation, series, publication |
| `hexafire_web/` | Static web application (HTML, CSS, JavaScript) |
| `telecharger_archives.sh` | Download of the MODIS and VIIRS monthly archives |
| `publier_site.sh` | Deployment of the application and its data to GitHub Pages (`gh-pages` branch) |
| `HEXAFIRE_document_en.pdf`, `HEXAFIRE_document.pdf` | Research document, in English and French |
| `DATA_SOURCES.md` | Data provenance and terms of use |

Supplementary material in French: technical dossier (`hexafire_web/docs/DOSSIER_TECHNIQUE.pdf`), user guide
(`hexafire_web/docs/GUIDE_UTILISATEUR.pdf`), engine run guide (`hexafire_moteur/GUIDE_EXECUTION.md`).

Raw and intermediate data (several tens of GB) are not versioned. The engine rebuilds them.

## Running it

Requires Python 3.11 or later.

```bash
cd hexafire_moteur
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                                  # 14 tests

python -m hexafire publier --exemple       # small fictitious dataset, to try the application
cd ../hexafire_web && python3 -m http.server 8000
# open http://localhost:8000  (English: http://localhost:8000/#l=en)
```

Full pipeline on real data, after `telecharger_archives.sh`:

```bash
python -m hexafire inventaire
python -m hexafire preparer
python -m hexafire agreger
python -m hexafire occasions
python -m hexafire calibrer
python -m hexafire valider
FIRMS_MAP_KEY=<your key> python -m hexafire firms     # optional: months after the latest archive
python -m hexafire serie
python -m hexafire publier
```

## Limitations

- A hotspot is not a wildfire, and the absence of hotspots does not prove the absence of fire. Clouds and smoke
  hide some fires.
- Overpasses are computed with an analytical formula, not yet from the real granule footprints of NASA's CMR catalogue.
- Strata are regular 10° blocks, not yet ecological regions.
- The interval covers the uncertainty of the conversion, not the natural variability of counts.
- The published series ends in August 2026. August 2025 and the 2026 months are based on MODIS and flagged as
  provisional until the corresponding VIIRS archives are processed.
- The CSV export gives monthly values per 0.25° cell. Individual detections are not republished; they remain
  available from NASA FIRMS.
- Ground-reported fires are not included, as no consistent source exists.

## Use of AI tools

As required by the Space Apps rules, we state where AI was used. The team worked with Claude (Anthropic), an AI
assistant, through the Claude desktop app.

- **Code.** Most of the Python engine (`hexafire_moteur/`) and of the web application (`hexafire_web/`) was written
  with Claude's help, from the team's specifications. The team ran it on the real data, tested it (14 automated
  tests) and reported the errors that were then fixed. Every source file starts with a line stating this.
- **Research and analysis.** Literature search, critical review of the method, help with reading the calibration
  and validation outputs.
- **Writing.** Drafting, editing and French–English translation of the research document, the technical dossier,
  the user guide and this README.

The choice of method, the processing runs, the validation and the results were decided, run and checked by the
team. No image, video or audio in this project was generated with AI. The screenshots in the user guide are captures
of the real application.

## Team

Team HEXAFIRE, ENSGMM, UNSTIM, Abomey, Benin.
