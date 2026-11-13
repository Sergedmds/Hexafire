---
title: "HEXAFIRE — Fiche technique de l'application web"
subtitle: "Calendrier harmonisé des points chauds MODIS + VIIRS, 2000 → aujourd'hui"
author: "Équipe HEXAFIRE — NASA Space Apps Challenge 2026"
date: "Version 1.2 — 13 novembre 2026"
lang: fr
---

# 1. Objet

HEXAFIRE est une application web qui affiche, pour une zone choisie n'importe où dans le monde, le calendrier mensuel du nombre de points chauds de novembre 2000 à aujourd'hui. Les détections MODIS et VIIRS y sont exprimées sur une seule échelle, de sorte que le capteur d'origine n'influence plus la lecture. Elle répond à la seconde partie du défi « Harmonization of MODIS and VIIRS Hot Spots » : une application qui prend en entrée des points chauds harmonisés.

**Publics** : services d'alerte précoce et de secours, pompiers, gestionnaires de terres, scientifiques.

**Ce que l'application n'est pas** : un système d'alerte en temps réel, un outil de comptage des incendies ou d'estimation des surfaces brûlées. Elle aide à reconnaître un écart par rapport à l'historique.

# 2. Principes d'interface (inspirés de NASA POWER)

L'interface reprend l'organisation du *Data Access Viewer* de NASA POWER, familière aux utilisateurs des données de la NASA :

| NASA POWER (DAV) | HEXAFIRE |
|---|---|
| Carte plein écran | Carte plein écran (MapLibre), fond clair, couche des points chauds du mois sélectionné |
| Panneau latéral à étapes numérotées | Panneau gauche repliable : 1. Zone · 2. Période · 3. Affichage · 4. Sorties · bouton **Afficher le calendrier** |
| Choix d'un point (clic ou lat/lon) ou d'une région (boîte) | Point + rayon, rectangle, polygone, pays ; saisie de coordonnées |
| Niveau temporel, période | Période (année de début et de fin), mois de référence ; pas de temps mensuel (journalier indicatif) |
| Paramètres | Grandeur affichée : nombre harmonisé ou écart à la normale ; unité équivalent MODIS ou équivalent VIIRS |
| Résultats : graphiques par paramètre, téléchargements CSV/JSON | Panneau de résultats : calendrier, indicateurs, analyses ; exports CSV, JSON, PNG, SVG |
| URL de la requête affichée | Lien partageable : zone et options encodées dans l'URL |
| Outils : recherche de lieu, fond de carte, « ma position », thème | Recherche de lieu, fond de carte, « ma position », thème clair/sombre, français/anglais |
| Visualize (couches mensuelles) | Couche « anomalie du mois » sur la carte (une couleur par cellule de 0,25°) |

**Parcours type (3 à 4 minutes)** : l'utilisateur trace son département ou saisit un point avec un rayon, choisit la période, clique sur *Afficher*. Le panneau de résultats s'ouvre sur le calendrier de 26 ans. Il bascule en « écart à la normale », survole une case pour lire sa valeur et son statut, ouvre l'onglet *Capteurs* pour voir la preuve de l'harmonisation, puis télécharge le CSV.

# 3. Écrans

## 3.1 Panneau latéral (étapes)

1. **Zone** — point + rayon (15 à 2 000 km), rectangle (2 clics), polygone, pays ; emprise nord/sud/est/ouest. Résumé : nombre de cellules de 0,25° retenues. Avertissement si la zone est plus petite qu'une cellule.
2. **Période** — début, fin, raccourcis (12 derniers mois, depuis 2000). La normale reste 2003–2020.
3. **Affichage** — niveau d'activité / écart à la normale ; unité équivalent MODIS / équivalent VIIRS (S-NPP). Le seuil « médiane ≥ 5 » est toujours appliqué en équivalent MODIS, pour qu'un mois soit accepté ou refusé quelle que soit l'unité.
4. **Sorties** — CSV du calendrier, CSV cellules de 0,25° × mois (deux unités et détections brutes), JSON, image PNG ou SVG.

**Carte du mois** (boîte flottante, comme la fonction *Visualize* de POWER) : couche « points chauds » ou « écart à la normale » sur une grille de 1°, curseur des mois, infobulle au survol. **Outils** : français / anglais, thème clair / sombre, recherche de lieu (OpenStreetMap Nominatim).

## 3.2 Panneau de résultats (onglets)

| Onglet | Contenu | Exigences du défi |
|---|---|---|
| **Calendrier** | Grille années × mois (année récente en haut) ; 4 indicateurs : dernier mois, écart à la normale, mois de pic habituel, rang de l'année ; infobulle (valeur, médiane, statut, source, couverture) | E2, E3, E9, E15 |
| **Analyses** | Profil saisonnier (médiane et quartiles), classement des années, saison cumulée en cours vs enveloppe des saisons passées, mois les plus inhabituels | E10 à E13 |
| **Capteurs** | Séries brutes par capteur, bascule brut / harmonisé (la marche disparaît), tableau de validation (kappa, fausses anomalies, comparaison M0, M1) | E1 |
| **Méthode** | Fiches courtes : point chaud, MODIS vs VIIRS, harmonisation, anomalie, ce que les satellites ne voient pas | E14, E16 |

## 3.3 Codage visuel

- **Niveau** : rampe séquentielle OrRd en échelle logarithmique.
- **Écart à la normale** : 5 classes, rampe divergente RdBu (très inférieure < 0,5 ; inférieure ; normale 0,8–1,25 ; supérieure ; très supérieure > 2).
- **Statut** porté par une texture, jamais par la seule couleur : triangle = converti ou provisoire ; hachures = couverture partielle ou non observé ; point = aucun point chaud.
- Accessibilité visée : contraste WCAG AA, navigation au clavier, textes alternatifs ; calendrier pivoté sur téléphone (mois en lignes).

# 4. Architecture technique

| Élément | Choix |
|---|---|
| Type | Site statique, sans serveur ni base de données, sans étape de compilation |
| Langages | HTML, CSS, JavaScript (modules ES) |
| Carte | MapLibre GL JS 4.7 + fond OpenStreetMap (chargés depuis Internet ; repli : saisie de coordonnées) |
| Graphiques | SVG généré à la main (calendrier) ; Observable Plot envisagé pour les analyses |
| Données | Fichiers JSON produits par le moteur (`python -m hexafire publier`), tuiles de 5° × 5° |
| Hébergement | GitHub Pages (ou Netlify) ; local : `python3 -m http.server 8000` |

**Modules** : `main.js` (état, branchements), `i18n.js` (textes FR/EN), `donnees.js` (index, tuiles, cartes mensuelles, série d'une zone), `calendrier.js` (statistiques, dessin), `graphiques.js` (analyses), `carte.js` (carte, tracés, couche du mois), `lien.js`, `export.js`.

**Calcul d'une zone** : le navigateur charge seulement les tuiles qui touchent l'emprise de la zone, retient les cellules dont le centre est dans la zone, et additionne leurs valeurs mois par mois. Médiane, rapport à la médiane, classes et rang sont calculés dans le navigateur.

# 5. Format d'échange des données (v2)

**`donnees/index.json`** :

- `format` (2), `genere_le`, `unite`, `unites` (`modis`, `viirs`), `pas_grille` (0,25), `taille_tuile` (5), `periode_reference` ([2003, 2020]), `carte` (`pas` = 1, `modele` = `cartes/m_{t}.json`) ;
- `mois` : liste ordonnée, `t` = 0 pour novembre 2000, avec `annee`, `mois`, `statut` (mesuré, converti, provisoire, couverture partielle, non observé), `source`, `couverture` ;
- `tuiles` : identifiants `ilat_ilon` des tuiles publiées ;
- `validation` : tableau des résultats (si disponible) ; `exemple` : vrai si données fictives.

**`donnees/tuiles/t_<ilat>_<ilon>.json`** : `{"cellules", "t", "v", "b", "w"}` ; `v` en équivalent MODIS (jour + nuit), `w` en équivalent VIIRS S-NPP, `b` détections brutes de la source du mois. Une cellule absente pour un mois observé vaut 0.

**`donnees/cartes/m_<t>.json`** : couche du mois `t` sur une grille de 1° : `{"c", "v", "w", "r"}`, `r` = rapport à la médiane 2003–2020 du même mois, −1 si non calculable. Cellules écrites : activité non nulle ou médiane ≥ 5 (les mois très inférieurs à la normale apparaissent donc aussi).

**Équivalent VIIRS** : w = N_harm × exp(α_S-NPP) × E_S-NPP / (E_Terra + E_Aqua), l'inverse exact de la conversion (mêmes facteurs, mêmes occasions) : ce que S-NPP seul aurait détecté. Test : sur la période VIIRS, w retrouve les détections S-NPP brutes à ± 10 %.

**À ajouter** : tirages d'incertitude des valeurs converties ; points chauds individuels pondérés (export, volume à étudier).

# 6. Exigences de qualité

| N° | Exigence | Cible |
|---|---|---|
| Q1 | Affichage du calendrier d'une zone après chargement des tuiles | < 2 s |
| Q2 | Taille d'une tuile publiée | < 2 Mo |
| Q3 | Fonctionnement sans connexion (après premier chargement) | oui, sauf la carte |
| Q4 | Aucune clé ni donnée personnelle dans les fichiers publiés | oui |
| Q5 | Export CSV avec en-tête de provenance (zone, unité, période de référence, date des données) | oui |
| Q6 | Mention permanente « un point chaud n'est pas un incendie » | oui |
| Q7 | Remerciement NASA FIRMS (onglet Méthode, exports) et provenance des données (`DATA_SOURCES.md`) | oui |

# 7. État au 13 novembre 2026

**Fait** :
- mise en page façon NASA POWER ;
- zones point + rayon (avec recherche de lieu), rectangle, polygone, pays ;
- période ;
- calendrier niveau / écart à la normale, avec textures de statut ;
- unités équivalent MODIS et équivalent VIIRS ;
- 4 indicateurs (le rang tient compte de la période choisie) ;
- onglets Analyses, Capteurs (validation réelle), Méthode (sources et remerciement FIRMS) ;
- couche « Carte du mois » ;
- version anglaise, thème sombre ;
- lien partageable ;
- exports avec provenance ;
- affichage sur téléphone.

**Testé** : navigateur automatisé sur données d'exemple, puis navigateur de l'équipe sur la **série réelle**
(novembre 2000 – juin 2024) avec la vraie carte. Test à distance par un membre de l'équipe via un tunnel temporaire.

**Documentation** : guide d'utilisation illustré (`docs/GUIDE_UTILISATEUR.pdf`) ; dossier technique complet
(`docs/DOSSIER_TECHNIQUE.pdf` : architecture, dépendances, modèles mathématiques, formats, résultats).

**À faire** :

| Priorité | Tâche |
|---|---|
| 1 | Publier la série complète (S-NPP 2021–2026) et vérifier plusieurs régions |
| 1 | Mise en ligne (GitHub Pages, `publier_site.sh`) ; ajouter `donnees/pays.geojson` |
| 2 | Retours des testeurs ; captures réelles dans le guide d'utilisation |
| 2 | Calendrier pivoté sur téléphone ; incertitude affichée pour les mois convertis |
| 3 | Export des détections individuelles (volume à étudier) |
