#!/usr/bin/env bash
# Met en ligne l'application HEXAFIRE sur GitHub Pages (branche gh-pages).
#
# Le code est sur la branche main ; les données publiées (hexafire_web/donnees, ~200 Mo)
# ne sont pas dans main. Ce script copie hexafire_web avec ses données dans un dossier
# temporaire et remplace entièrement la branche gh-pages (push forcé, un seul commit) :
# l'historique ne grossit pas à chaque mise à jour des données.
#
# Usage : ./publier_site.sh     (depuis n'importe où, après python -m hexafire publier)
set -euo pipefail

RACINE="$(cd "$(dirname "$0")" && pwd)"
WEB="$RACINE/hexafire_web"
DEPOT="$(git -C "$RACINE" remote get-url origin)"

[ -f "$WEB/donnees/index.json" ] || { echo "Pas de données : lancez d'abord  python -m hexafire publier"; exit 1; }
if grep -q '"exemple": true' "$WEB/donnees/index.json"; then
  read -r -p "ATTENTION : ce sont les données d'EXEMPLE (fictives). Publier quand même ? [o/N] " r
  [ "$r" = "o" ] || exit 1
fi
[ -f "$WEB/donnees/pays.geojson" ] || echo "Remarque : donnees/pays.geojson absent, le choix par pays sera indisponible en ligne."

# GitHub refuse les fichiers de plus de 100 Mo
GROS="$(find "$WEB/donnees" -type f -size +95M)"
[ -z "$GROS" ] || { echo "Fichiers trop gros pour GitHub :"; echo "$GROS"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# Seuls les fichiers servis par le site sont publiés (pas les documents, sources ni fichiers de travail)
cp "$WEB/index.html" "$TMP/"
cp -r "$WEB/css" "$WEB/js" "$WEB/donnees" "$TMP/"
touch "$TMP/.nojekyll"          # servir les fichiers tels quels (pas de traitement Jekyll)
echo "Taille du site : $(du -sh "$TMP" | cut -f1)"

cd "$TMP"
git init -q
git checkout -q -b gh-pages
git add -A
git commit -q -m "Site HEXAFIRE ($(date +%Y-%m-%d))"
git push -f "$DEPOT" gh-pages
echo "Publié sur https://sergedmds.github.io/Hexafire/ (mise à jour en une à deux minutes)."
