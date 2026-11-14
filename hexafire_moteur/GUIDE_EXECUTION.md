# Faire tourner le moteur HEXAFIRE depuis le début

Ce guide décrit la chaîne complète, des archives téléchargées jusqu'aux fichiers de l'application web.
Pour chaque étape : ce qu'elle fait, la commande, ce qui s'affiche et comment le lire. Les modèles mathématiques de
chaque étape sont détaillés dans `hexafire_web/docs/DOSSIER_TECHNIQUE.pdf` (section 5).

## 0. Avant de commencer

**Installation (une fois).** Il faut Python 3.11 ou plus récent, et `lftp` pour le téléchargement.

```bash
sudo apt install lftp                      # Ubuntu / Debian
cd ~/Documents/Hackathon_NASA_2026/hexafire_moteur
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # pandas, numpy, pyarrow, requests, pytest
```

**Téléchargement des archives** (serveur SFTP de l'université du Maryland ; provenance : `DATA_SOURCES.md`) :

```bash
cd ~/Documents/Hackathon_NASA_2026
bash telecharger_archives.sh modis              # MODIS collection 6, 2000-2022
bash telecharger_archives.sh modis_recent       # MODIS collection 6.1, 2023 ->
bash telecharger_archives.sh snpp               # VIIRS S-NPP 2012 -> (indispensable : calibration et 2021 ->)
bash telecharger_archives.sh noaa21             # facultatif : relais après l'arrêt de S-NPP
bash telecharger_archives.sh noaa20             # facultatif
for f in donnees_brutes/*/*.gz; do gzip -t "$f" 2>/dev/null || echo "ABÎMÉ : $f"; done   # contrôle
```

Le téléchargement reprend là où il s'est arrêté. Un fichier coupé et daté plus récemment que celui du serveur n'est
pas retéléchargé : supprimez-le puis relancez la commande.

**Vérification de l'installation** :

```bash
cd ~/Documents/Hackathon_NASA_2026/hexafire_moteur
source .venv/bin/activate          # (.venv) doit apparaître au début de la ligne
pytest -q                          # attendu : 14 passed
```

Si un test échoue, ne lancez pas la chaîne : le code ou l'environnement a un problème.

**Dossiers utilisés** (réglés dans `config.toml`, à côté de `hexafire_moteur/`) :

| Dossier | Contenu | Écrit par |
|---|---|---|
| `donnees_brutes/` | archives mensuelles MODIS et VIIRS (`.txt.gz`, `.csv.gz`) | `telecharger_archives.sh`, `firms` |
| `donnees_preparees/` | détections filtrées, un fichier par capteur et par mois | `preparer`, `firms` |
| `agregats/` | tables de comptage, occasions, facteurs, série harmonisée | `agreger` à `serie` |
| `journaux/` | journal de préparation, résultats de validation | `preparer`, `valider` |
| `../hexafire_web/donnees/` | fichiers lus par l'application | `publier` |

**Réglages importants** (`config.toml`) : grille de 0,25° ; on garde les feux de végétation (type 0), les
détections MODIS de confiance ≥ 30 et les VIIRS hors confiance « faible » ; normale 2003–2020 ;
calibration 2012–2020 ; passage à VIIRS en janvier 2021.

## Vue d'ensemble

```
inventaire → preparer → (firms) → agreger → occasions → calibrer → valider → serie → publier
```

Chaîne complète en une ligne (s'arrête à la première erreur) :

```bash
python -m hexafire preparer && python -m hexafire agreger && python -m hexafire occasions \
 && python -m hexafire calibrer && python -m hexafire valider && python -m hexafire serie \
 && python -m hexafire publier
```

**Règle d'or : après chaque `agreger`, relancez `occasions`.** Sinon `calibrer` exclut les nouveaux mois
(voir l'étape 5).

---

## 1. `inventaire`, ce qui sera utilisé

**Ce que ça fait**. Parcourt `donnees_brutes/`, reconnaît chaque archive (produit, année, mois, version)
et dit ce qui sera utilisé. Ne modifie rien. Si deux versions du même mois existent, la plus récente
est retenue (MODIS : collection 6 jusqu'en 2022, 6.1 ensuite).

```bash
python -m hexafire inventaire
```

**Sortie** :
```
Dossier : /home/.../donnees_brutes
  MCD14ML      310 mois  (2000-11 -> 2026-08)
  VNP14IMGML   176 mois  (2012-01 -> 2026-07)
  ...
```

**Comment la lire** :
- une ligne par produit : nombre de mois, premier et dernier mois ;
- MCD14ML devrait couvrir 2000-11 → 2026-08 (environ 310 mois) ;
- pour calibrer, il faut **VNP14IMGML de 2012 à 2020** (108 mois) ;
- un trou (moins de mois que l'intervalle) signale un fichier manquant ou encore en téléchargement.

## 2. `preparer`, filtrer et ranger les détections

**Ce que ça fait**. Lit chaque archive, garde uniquement les détections utiles (type 0, confiance),
les met dans un format commun et écrit un fichier par capteur (Terra, Aqua, S-NPP, NOAA-20, NOAA-21)
et par mois dans `donnees_preparees/`. Chaque archive traitée est notée dans
`journaux/preparation.jsonl` avec son empreinte : **relancer ne refait que les nouvelles archives**.

```bash
python -m hexafire preparer                         # tout
python -m hexafire preparer --produits MCD14ML      # un seul produit
python -m hexafire preparer --limite 3              # essai sur 3 archives
python -m hexafire preparer --forcer                # tout refaire (après changement de filtres)
```

**Sortie** :
```
[12/486] MCD14ML.201203.006.03.txt.gz :   312,455 lues,   268,910 retenues (4.2 s)
[13/486] VNP14IMGML.201203.C2.04.csv.gz : ignorée (EOFError: ...)
486 archive(s) préparée(s). Journal : .../journaux/preparation.jsonl
```

**Comment la lire** :
- `lues` / `retenues` : la part retenue tourne en général autour de **80 à 95 %** pour MODIS (on retire les
  volcans, sources fixes et faibles confiances). Pour VIIRS elle est un peu plus basse (classe « faible »
  retirée). Une part proche de 0 % ou de 100 % mérite une vérification ;
- `ignorée (EOFError…)` : archive incomplète, en général **encore en téléchargement**. Relancez
  `preparer` quand le téléchargement est fini ;
- une archive déjà préparée n'apparaît pas : c'est normal.

## 3. `firms` (facultatif), les mois les plus récents

**Ce que ça fait**. Télécharge par l'API FIRMS ce qui manque après la fin des archives du serveur
(MODIS après août 2026, VIIRS après juillet 2026), puis le prépare comme à l'étape 2 (fichiers
`<capteur>_<AAAAMM>_api`). Reprend là où il s'était arrêté. Peut tourner **en même temps** que les
téléchargements SFTP. À lancer **avant** `agreger`.

```bash
export FIRMS_MAP_KEY=votre_cle
python -m hexafire firms                    # télécharger et préparer
python -m hexafire firms --seulement-preparer
```

**Sortie** :
```
  MODIS : archive jusqu'au 2026-08-31, API à partir du 2026-09-01
  VIIRS_NOAA21_NRT 2026-08-01 +5 j : 61,204 détections
API FIRMS : 1,254,330 détections lues, 1,050,112 retenues, 12 fichiers capteur-mois écrits
```

**Comment la lire** :
- les premières lignes rappellent les dates de raccord archive / API ;
- `réponse inattendue` : clé invalide, quota dépassé (5 000 requêtes par 10 min) ou service indisponible.
  Attendez quelques minutes et relancez ;
- quand l'archive d'un mois arrive plus tard, `agreger` ignore automatiquement la version API de ce mois.

## 4. `agreger`, compter par cellule et par mois

**Ce que ça fait**. Compte les détections par cellule de 0,25°, mois, capteur et période (jour/nuit).
C'est la table de base de tout le reste (`agregats/cell_month`). Elle produit aussi les comptages
mondiaux par jour (`capteur_jour`), qui servent à repérer les jours sans données, et un résumé
`agregats/resume_mensuel.csv`.

```bash
python -m hexafire agreger
```

**Sortie** :
```
  3 mois API ignorés (archive disponible)
  100/486 fichiers agrégés
cell_month : 48,215,330 lignes, 512,904,118 détections -> .../agregats/cell_month.parquet
```

**Comment la lire** :
- le total de détections doit être **proche de la somme des « retenues »** de l'étape 2 ;
- ouvrez `resume_mensuel.csv` (tableur) : un mois avec beaucoup moins de détections que ses voisins
  signale un fichier incomplet ou une panne du satellite.

## 5. `occasions`, combien de fois chaque cellule a été vue

**Ce que ça fait**. Calcule le nombre de passages de chaque satellite au-dessus de chaque cellule (selon la
latitude et la fauchée) et repère les **jours sans données**. Un jour compte comme manquant quand le
capteur détecte moins de 10 % de son activité mondiale habituelle. Sans ce calcul, on confondrait
« moins de feux » et « moins de passages ».

```bash
python -m hexafire occasions
```

**Sortie** :
```
occasions : 412,880 cellules actives, 1,104 capteur-mois -> .../agregats
  37 capteur-mois incomplets, par exemple :
 capteur  annee  mois  jours_mois  jours_disponibles
   Terra   2001     6          30                 15
    Aqua   2002     7          31                  5
   S-NPP   2012     1          31                 19
```

**Comment la lire** :
- `capteur-mois` = nombre de mois connus, tous capteurs confondus ;
- la liste des mois incomplets doit correspondre à des **pannes connues** : Terra juin 2001, début d'Aqua
  en juillet 2002, début de S-NPP en janvier 2012, arrêt de S-NPP en novembre 2026. Ces mois sont
  corrigés par le nombre de jours réels. Sous 80 % de jours, ils seront marqués
  « couverture partielle », et « non observé » sous 30 %.

## 6. `calibrer`, apprendre le facteur VIIRS → MODIS

**Ce que ça fait**. Sur 2012–2020, quand MODIS et S-NPP observaient ensemble, estime combien un point chaud
S-NPP vaut de points chauds MODIS, à nombre de passages égal. Le facteur est estimé par strate (bloc de 10°),
mois de l'année et jour/nuit, puis stabilisé (estimations peu sûres rapprochées de la valeur annuelle de la
strate). Raccorde ensuite NOAA-20 et NOAA-21 à S-NPP sur leurs années communes.

```bash
python -m hexafire calibrer           # --bloc 5 pour des strates de 5°
```

**Sortie** :
```
Calibration S-NPP -> MODIS sur 2012-2020 (9 année(s)), 2,104,556 couples cellule-mois, 328 strates
  jour : 1 point chaud S-NPP = 0.185 point chaud MODIS (médiane des strates ; 10 %-90 % : 0.120-0.260)
  nuit : 1 point chaud S-NPP = 0.064 point chaud MODIS (médiane des strates ; 10 %-90 % : 0.030-0.110)
  -> .../agregats/conversion_snpp.parquet
  NOAA-20 raccordé à S-NPP sur [2018, ..., 2026] : 1 point chaud NOAA-20 = 0.950 (jour) / 0.930 (nuit) point chaud S-NPP
  NOAA-21 raccordé à S-NPP sur [2023, ..., 2026] : ...
```

**Comment la lire** :
- **jour**. Facteur attendu entre **0,15 et 0,25** (VIIRS voit 4 à 7 fois plus de points chauds que MODIS).
  Premiers résultats 2012–2013 : 0,185, soit 5,4 fois ;
- **nuit**. Facteur plus faible, autour de **0,05 à 0,10** (10 à 20 fois plus). Premier résultat : 0,064 ;
- l'intervalle 10 %–90 % montre la variation entre régions : c'est justement ce qu'un facteur unique raterait ;
- **NOAA-20 et NOAA-21**. Facteur proche de **1** (même instrument que S-NPP). Un écart de ±10 % est plausible.
  Un écart beaucoup plus grand est suspect ;
- `attention : … couples sans occasions connues, exclus` : vous n'avez pas relancé `occasions` après
  `agreger`. Relancez `occasions`, puis `calibrer` ;
- **facteurs à 0,000** ou erreur de logarithme : même cause (occasions manquantes) ;
- `pas encore de recouvrement avec S-NPP` : les fichiers NOAA ne sont pas encore préparés. Ce n'est pas
  bloquant.

## 7. `valider`, vérifier que la conversion donne les bons verdicts

**Ce que ça fait**. Pour chaque année de 2012 à 2020, refait la calibration **sans cette année**, convertit
VIIRS pour cette année-là et compare au vrai MODIS. On compare le verdict de chaque mois (bas / normal /
haut par rapport aux seuils 10 % et 90 % de 2003–2011) avec trois méthodes :
- **HEXAFIRE**. Notre conversion ;
- **M1**. Un seul facteur pour le monde ;
- **M0**. VIIRS brut, sans conversion.

```bash
python -m hexafire valider
```

**Sortie** (exemple réel sur 2012–2013) :
```
Validation « une année exclue » sur 2012, 2013 : 5,830 strate-mois comparés
          methode  kappa  accord  fausses_anomalies  biais_median  erreur_mediane  marche_max_annee  ic95_kappa_H_moins_methode
         HEXAFIRE  0.645   ...              0.157         0.016           0.182             0.066
M1 facteur global  0.543   ...              0.236         0.024           0.245             0.108   [0.060 ; 0.140]
  M0 raccord brut  0.013   ...              0.924         1.946           1.946             1.979   [0.580 ; 0.680]
```

**Comment lire chaque colonne** :

| Colonne | Sens | Cible |
|---|---|---|
| `kappa` | accord des verdicts avec MODIS, corrigé du hasard (0 = hasard, 1 = parfait) | ≥ 0,5 |
| `accord` | part des mois où le verdict est identique | indicatif |
| `fausses_anomalies` | part des mois normaux pour MODIS que la méthode déclare bas ou haut | ≤ 0,15 |
| `biais_median` | écart systématique (en log) : > 0 surestime, < 0 sous-estime | \|·\| < 0,10 |
| `erreur_mediane` | écart typique d'un mois (en log ; 0,18 ≈ 20 %) | < 0,25 |
| `marche_max_annee` | plus grand saut moyen d'une année : mesure la « fausse marche » au changement de capteur | < 0,10 |
| `ic95_kappa_H_moins_methode` | intervalle de confiance à 95 % de kappa(HEXAFIRE) − kappa(méthode) | entièrement > 0 |

**Verdict** :
- HEXAFIRE est **meilleur que M1** si l'intervalle de la ligne M1 est entièrement positif ;
- **M0** doit être très mauvais (kappa proche de 0, biais proche de 2). C'est la preuve que sans harmonisation,
  la série est inutilisable ;
- avec moins de 4 années testées, le programme prévient que les intervalles sont **indicatifs** ;
- fichiers écrits dans `journaux/` : `validation_resultats.csv` (le tableau, repris par l'application) et
  `validation_detail.csv.gz` (chaque strate-mois, pour creuser une région).

## 8. `serie`, construire la série harmonisée de 2000 à aujourd'hui

**Ce que ça fait**. Assemble une seule série, en équivalent MODIS, pour chaque cellule et chaque mois.
Chaque valeur est ramenée au même nombre de passages (médiane 2003–2020).

| Période | Source | Statut |
|---|---|---|
| nov. 2000 – juin 2002 | Terra seul, ramené à Terra + Aqua | converti |
| juil. 2002 – déc. 2020 | MODIS Terra + Aqua | mesuré |
| depuis janv. 2021 | VIIRS converti (moyenne pondérée de S-NPP, NOAA-20, NOAA-21) | converti |
| mois sans VIIRS disponible | MODIS | provisoire |

```bash
python -m hexafire serie
```

**Sortie** :
```
Série harmonisée : 31,502,118 cellules-mois non nulles, 98,450,220 points chauds équivalent MODIS -> .../harmonized_cell_month.parquet
statut
mesuré                  218
converti                 70
couverture partielle      2
provisoire                1
```

**Comment la lire** :
- le tableau compte les **mois** par statut. On attend environ 200 mois « mesuré » (juil. 2002 – déc. 2020), une
  vingtaine de « converti » pour Terra seul (nov. 2000 – juin 2002) et un « converti » par mois depuis 2021 ;
- `couverture partielle` doit correspondre aux pannes vues à l'étape 5 ;
- `provisoire` : mois sans VIIRS encore (par exemple VIIRS pas fini de télécharger). Ils deviendront
  « converti » après un nouveau passage de la chaîne ;
- contrôle visuel : dans l'onglet **Capteurs** de l'application, la courbe harmonisée ne doit **pas
  sauter** en 2021, contrairement à la courbe brute.

## 9. `publier`, préparer les fichiers de l'application

**Ce que ça fait**. Écrit dans `../hexafire_web/donnees/` :
- `index.json` (mois, statuts, validation) ;
- les tuiles de 5° (équivalent MODIS, équivalent VIIRS, brut) ;
- les cartes mensuelles de 1° (valeur et rapport à la normale).

```bash
python -m hexafire publier            # série réelle
python -m hexafire publier --exemple  # jeu fictif, pour tester l'interface sans données
```

**Sortie** :
```
Publication : 1,820 tuiles, 9,240,115 valeurs, 311 mois, 309 cartes -> .../hexafire_web/donnees
```

**Comment la lire** :
- `tuiles` : nombre de carrés de 5° qui ont au moins un point chaud (au plus 2 592) ;
- `mois` : nombre de mois de la série ; `cartes` : mois observés (les « non observé » n'ont pas de carte) ;
- `conversion_snpp absente : unité équivalent VIIRS non publiée` : `calibrer` n'a pas tourné. L'application
  marche, mais sans l'unité VIIRS ;
- avec `--exemple`, l'application affiche le bandeau « Données d'exemple (fictives) ». Il disparaît avec la
  série réelle.

Puis :
```bash
cd ../hexafire_web && python3 -m http.server 8000     # ouvrir http://localhost:8000
```

---

## Quand relancer quoi ?

| Situation | À relancer |
|---|---|
| De nouvelles archives sont arrivées | `preparer` → `agreger` → `occasions` → `calibrer` → `valider` → `serie` → `publier` |
| Nouveaux mois via l'API FIRMS | `firms` → `agreger` → `occasions` → `serie` → `publier` |
| Filtres modifiés dans `config.toml` | `preparer --forcer` puis toute la suite |
| Taille des strates modifiée (`--bloc`) | `calibrer --bloc X` → `valider --bloc X` → `serie --bloc X` → `publier --bloc X` |
| Seule l'application a changé | rien (éventuellement `publier`) |

## Problèmes fréquents

| Message | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'hexafire'` | lancé hors de `hexafire_moteur`, ou ancien pytest | `cd hexafire_moteur`, puis `python -m ...` |
| `no tests ran` | pytest lancé depuis un autre dossier | lancer depuis `hexafire_moteur` |
| `ignorée (EOFError …)` | archive en cours de téléchargement | relancer `preparer` plus tard |
| `couples sans occasions connues` / facteurs 0,000 | `occasions` pas relancé après `agreger` | `occasions` puis `calibrer` |
| `Aucun couple MODIS / S-NPP sur la période de calibration` | pas de S-NPP 2012–2020 préparé | télécharger, `preparer`, `agreger`, `occasions` |
| `Clé FIRMS manquante` | variable non définie | `export FIRMS_MAP_KEY=...` dans le même terminal |
| `index.json introuvable` dans l'application | `publier` pas lancé | `python -m hexafire publier` (ou `--exemple`) |
