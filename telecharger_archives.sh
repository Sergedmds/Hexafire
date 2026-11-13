#!/usr/bin/env bash
# HEXAFIRE - Téléchargement des archives mensuelles mondiales de feux actifs
# Serveur SFTP de l'Université du Maryland (identifiants publics : fire / burnt)
#
# Prérequis : sudo apt install lftp
#
# Utilisation (depuis le dossier Hackathon_NASA_2026) :
#   bash telecharger_archives.sh lister    # affiche les dossiers VIIRS et la taille des fichiers
#   bash telecharger_archives.sh explorer  # contenu des dossiers MODIS (recherche des années 2000-2022)
#   bash telecharger_archives.sh versions  # inventaire : nb de fichiers, 1er/dernier mois, versions, disque libre
#   bash telecharger_archives.sh modis     # MODIS Terra + Aqua (MCD14ML C6), nov. 2000 -> déc. 2022
#   bash telecharger_archives.sh modis_recent  # MODIS C6.1, janv. 2023 -> dernier mois (test de dérive)
#   bash telecharger_archives.sh snpp_calibration  # S-NPP 2012-2020 seulement (prioritaire)
#   bash telecharger_archives.sh snpp      # VIIRS Suomi NPP (VNP14IMGML C2), tous les mois
#   bash telecharger_archives.sh noaa20    # VIIRS NOAA-20 (VJ114IMGML C2)
#   bash telecharger_archives.sh noaa21    # VIIRS NOAA-21 (VJ214IMGML C2)
#   bash telecharger_archives.sh tout      # tout, dans cet ordre
#
# Le script peut être interrompu (Ctrl+C) et relancé : il reprend les fichiers
# incomplets et ne retélécharge pas ceux qui sont déjà là.

set -uo pipefail

HOTE="sftp://fuoco.geog.umd.edu"
UTIL="fire,burnt"
DEST="${DEST:-$(pwd)/donnees_brutes}"
PARALLELE="${PARALLELE:-3}"   # nombre de fichiers téléchargés en même temps

# Chemins sur le serveur. MODIS est confirmé ; les dossiers VIIRS sont à
# confirmer avec "lister" puis à corriger ici si besoin.
DOSSIER_MODIS="/data/MODIS/C61/MCD14ML"     # collection 6.1 : janv. 2023 -> aujourd'hui seulement
DOSSIER_MODIS_C6="/data/MODIS/C6/MCD14ML"   # collection 6   : nov. 2000 -> janv. 2023
DOSSIER_SNPP="/data/VIIRS/C2/VNP14IMGML"
DOSSIER_NOAA20="/data/VIIRS/C2/VJ114IMGML"
DOSSIER_NOAA21="/data/VIIRS/C2/VJ214IMGML"

REGLAGES="set sftp:auto-confirm yes; set net:max-retries 10; set net:reconnect-interval-base 15; set net:timeout 60"

miroir() {
  local source="$1" cible="$2" motif="$3"
  mkdir -p "$DEST/$cible"
  echo ">>> $source  ->  $DEST/$cible   (fichiers : $motif)"
  if ! lftp -u "$UTIL" "$HOTE" -e "$REGLAGES; mirror --continue --only-newer --parallel=$PARALLELE --include-glob '$motif' --log='$DEST/$cible/journal.txt' '$source' '$DEST/$cible'; bye"; then
    echo "!!! Échec pour $source (dossier introuvable ou connexion coupée). Relancez, ou vérifiez le chemin avec : bash $0 lister"
    return 1
  fi
  echo "    $(ls "$DEST/$cible" | grep -c '\.gz$') fichiers présents dans $DEST/$cible"
}

lister() {
  lftp -u "$UTIL" "$HOTE" -e "$REGLAGES; echo '--- /data/VIIRS/C2 ---'; cls -1 /data/VIIRS/C2/; echo '--- Taille de quelques fichiers S-NPP ---'; cls -lh '$DOSSIER_SNPP/*201901*'; cls -lh '$DOSSIER_SNPP/*202401*'; echo '--- Taille de quelques fichiers MODIS ---'; cls -lh '$DOSSIER_MODIS/*201901*'; bye"
}

# Inventaire : nombre de fichiers par dossier, premier et dernier mois, versions présentes
versions() {
  local d
  for d in "$DOSSIER_MODIS" "$DOSSIER_SNPP" "$DOSSIER_NOAA20" "$DOSSIER_NOAA21"; do
    echo "=== $d ==="
    lftp -u "$UTIL" "$HOTE" -e "$REGLAGES; cls -1 '$d/'; bye" 2>/dev/null \
      | sed 's#.*/##' | grep -E '\.gz$' > /tmp/hexafire_liste.txt || true
    echo "  fichiers : $(wc -l < /tmp/hexafire_liste.txt)"
    echo "  premier  : $(head -1 /tmp/hexafire_liste.txt)"
    echo "  dernier  : $(tail -1 /tmp/hexafire_liste.txt)"
    echo "  versions (nombre de fichiers par version) :"
    awk -F. '{print "    " $(NF-3) "." $(NF-2)}' /tmp/hexafire_liste.txt | sort | uniq -c
  done
  echo "=== Espace disque libre ==="
  df -h "$(pwd)" | tail -1
}

if ! command -v lftp >/dev/null 2>&1; then
  echo "lftp n'est pas installé. Installez-le avec : sudo apt install lftp"
  exit 1
fi

# Versions à télécharger (à ajuster d'après "versions")
V_MODIS="${V_MODIS:-061.*}"     # MODIS : toutes les versions présentes de la collection 6.1
V_VIIRS="${V_VIIRS:-C2.04}"     # VIIRS : version 04 (la plus récente constatée le 12/11/2026)

case "${1:-aide}" in
  lister)   lister ;;
  versions) versions ;;
  modis)    # 2000-2022 depuis la collection 6 (seule disponible sur ce serveur pour ces années)
            miroir "$DOSSIER_MODIS_C6" MCD14ML "MCD14ML.200*.006.03.txt.gz"
            miroir "$DOSSIER_MODIS_C6" MCD14ML "MCD14ML.201*.006.03.txt.gz"
            miroir "$DOSSIER_MODIS_C6" MCD14ML "MCD14ML.202[0-2]*.006.03.txt.gz" ;;
  modis_recent)  # 2023 -> aujourd'hui, collection 6.1 (utile seulement pour le test de dérive T9)
            miroir "$DOSSIER_MODIS"  MCD14ML    "MCD14ML.*.$V_MODIS.txt.gz" ;;
  snpp_calibration)   # S-NPP 2012-2020 seulement : la période de calibration, à prendre en premier
            miroir "$DOSSIER_SNPP"   VNP14IMGML "VNP14IMGML.201[2-9]*.$V_VIIRS.csv.gz"
            miroir "$DOSSIER_SNPP"   VNP14IMGML "VNP14IMGML.2020*.$V_VIIRS.csv.gz" ;;
  snpp)     miroir "$DOSSIER_SNPP"   VNP14IMGML "VNP14IMGML.*.$V_VIIRS.csv.gz" ;;
  noaa20)   miroir "$DOSSIER_NOAA20" VJ114IMGML "VJ114IMGML.*.$V_VIIRS.csv.gz" ;;
  noaa21)   miroir "$DOSSIER_NOAA21" VJ214IMGML "VJ214IMGML.*.$V_VIIRS.csv.gz" ;;
  explorer) # contenu brut (dossiers compris) des dossiers MODIS, pour trouver les années 2000-2022
            lftp -u "$UTIL" "$HOTE" -e "$REGLAGES; echo '--- /data/MODIS ---'; cls -1 /data/MODIS/; echo '--- /data/MODIS/C61 ---'; cls -1 /data/MODIS/C61/; echo '--- /data/MODIS/C61/MCD14ML (hors fichiers .gz) ---'; cls -1 /data/MODIS/C61/MCD14ML/ | grep -v '.gz$'; echo '--- /data/MODIS/C6/MCD14ML (5 premiers, 5 derniers) ---'; cls -1 /data/MODIS/C6/MCD14ML/ | head -5; cls -1 /data/MODIS/C6/MCD14ML/ | tail -5; bye" ;;
  tout)
    miroir "$DOSSIER_MODIS_C6" MCD14ML "MCD14ML.200*.006.03.txt.gz"
    miroir "$DOSSIER_MODIS_C6" MCD14ML "MCD14ML.201*.006.03.txt.gz"
    miroir "$DOSSIER_MODIS_C6" MCD14ML "MCD14ML.202[0-2]*.006.03.txt.gz"
    miroir "$DOSSIER_MODIS"    MCD14ML "MCD14ML.*.$V_MODIS.txt.gz"
    miroir "$DOSSIER_SNPP"   VNP14IMGML "VNP14IMGML.*.$V_VIIRS.csv.gz"
    miroir "$DOSSIER_NOAA20" VJ114IMGML "VJ114IMGML.*.$V_VIIRS.csv.gz"
    miroir "$DOSSIER_NOAA21" VJ214IMGML "VJ214IMGML.*.$V_VIIRS.csv.gz"
    ;;
  *) sed -n '2,22p' "$0" ;;
esac
