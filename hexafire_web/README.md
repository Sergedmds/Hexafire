# HEXAFIRE — application web (v0.3, mise en page façon NASA POWER)

Site **statique** : aucun serveur applicatif, aucune base de données, aucune étape de compilation.
Le navigateur lit les fichiers produits par le moteur (`../hexafire_moteur`) dans `donnees/`.

## Lancer en local

```bash
# 1. Produire des données (une seule fois)
cd ../hexafire_moteur && source .venv/bin/activate
python -m hexafire publier --exemple     # jeu FICTIF au bon format, pour développer l'interface
# ou, quand la série réelle est calculée (après calibrer et serie) :
python -m hexafire publier

# 2. Servir le site
cd ../hexafire_web
python3 -m http.server 8000
# puis ouvrir http://localhost:8000   (version anglaise : http://localhost:8000/#l=en)
```

La carte (MapLibre + fond OpenStreetMap) et la recherche de lieu (OpenStreetMap Nominatim) passent par
Internet. Sans connexion, l'application reste utilisable avec la saisie des coordonnées.

## Pays (facultatif)

Pour le choix d'un pays, téléchargez les frontières Natural Earth (1:110 M) et enregistrez-les sous
`donnees/pays.geojson` :

```bash
wget -O donnees/pays.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson
```

(`python -m hexafire publier` ne supprime pas ce fichier.)

## Organisation

| Fichier | Rôle |
|---|---|
| `index.html` | Carte plein écran, panneau à étapes (1 Zone, 2 Période, 3 Affichage, 4 Sorties), boîte « Carte du mois », panneau de résultats à onglets |
| `css/style.css` | Styles clair et sombre (suit le système, ou choix mémorisé), bureau et téléphone |
| `js/main.js` | État, étapes, onglets, indicateurs, unités, couche de la carte, recherche de lieu, thème, lien partagé |
| `js/i18n.js` | Textes français et anglais |
| `js/donnees.js` | Index, tuiles et cartes mensuelles ; zones cercle, rectangle, polygone, pays ; séries d'une zone |
| `js/calendrier.js` | Médiane historique, classes d'écart, calendrier SVG, légende |
| `js/graphiques.js` | Profil saisonnier, saison cumulée, brut vs harmonisé, tableaux (années, mois inhabituels, validation) |
| `js/carte.js` | Carte, tracés, couche mensuelle de 1°, fond clair / sombre |
| `js/lien.js` | Lien partageable (zone, mode, période, unité, langue dans l'adresse) |
| `js/export.js` | CSV du calendrier, CSV cellules × mois (deux unités), JSON, SVG, PNG |

## Format des données (v2) — produit par `hexafire/publication.py`

- `donnees/index.json` : `mois` (liste ; `t` = 0 pour novembre 2000, statut, source, couverture),
  `tuiles`, `unites` (`modis`, `viirs`), `carte` (`pas` = 1°, modèle de nom de fichier),
  `periode_reference`, `pas_grille`, `validation`, `exemple` (si fictif).
- `donnees/tuiles/t_<ilat>_<ilon>.json` : `{"cellules", "t", "v", "b", "w"}` — `v` équivalent MODIS,
  `w` équivalent VIIRS S-NPP, `b` détections brutes de la source du mois. Cellule absente = 0.
- `donnees/cartes/m_<t>.json` : `{"c", "v", "w", "r"}` sur une grille de 1° ; `r` = rapport à la médiane
  2003–2020 du même mois, `-1` si non calculable (moins de 10 ans de référence ou médiane < 5).

## Ce qui marche (testé dans Chromium ; la carte réelle n'a pas pu être chargée dans l'environnement de test)

Zones point + rayon (avec recherche de lieu), rectangle, polygone, pays ; période ; calendrier
(niveau / écart à la normale) ; unités équivalent MODIS et équivalent VIIRS ; 4 indicateurs ; onglets
Analyses, Capteurs, Méthode ; couche « Carte du mois » (points chauds ou écart, curseur des mois,
infobulle) ; français / anglais ; thème clair / sombre ; lien partageable ; exports ; téléphone (empilé).

## À faire

- Vérifier la carte réelle dans un navigateur connecté (couche du mois, fond sombre).
- Calendrier pivoté sur téléphone (mois en lignes).
- Export des détections individuelles (volume à étudier).
