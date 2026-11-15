// Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
// Textes de l'interface en français et en anglais.
// Dans le HTML : data-i18n="cle" (texte), data-i18n-html="cle" (HTML), data-i18n-title, data-i18n-aria, data-i18n-ph.

const T = {
  fr: {
    "titre": "HEXAFIRE, calendrier des feux",
    "sous_titre": "Points chauds MODIS + VIIRS harmonisés, 2000 → aujourd'hui",
    "exemple": "Données d'exemple (fictives)",
    "carte_aria": "Carte du monde où tracer ou choisir votre zone",
    "carte_absente": "Carte indisponible sans connexion. Saisissez les coordonnées dans le panneau.",
    "panneau_aria": "Paramètres de la recherche",
    "replier": "Replier le panneau",
    "theme": "Changer de thème (clair / sombre)",
    "langue": "English version", "theme_sombre": "Thème sombre", "theme_clair": "Thème clair",
    "e1": "Choisir la zone", "e2": "Choisir la période", "e3": "Choisir l'affichage", "e4": "Afficher et télécharger",
    "z_point": "Point", "z_rect": "Rectangle", "z_poly": "Polygone", "z_pays": "Pays",
    "aide_point": "Cliquez sur la carte, cherchez un lieu ou saisissez les coordonnées (degrés décimaux).",
    "lieu": "Rechercher un lieu", "lieu_ph": "ex. Parakou, Bénin", "lieu_aucun": "Lieu introuvable.",
    "lieu_erreur": "Recherche indisponible (pas de connexion).",
    "lat": "Latitude", "lon": "Longitude", "rayon": "Rayon (km)",
    "aide_rect": "Cliquez deux coins opposés sur la carte, ou saisissez l'emprise.",
    "nord": "Nord", "sud": "Sud", "ouest": "Ouest", "est": "Est",
    "aide_poly": "Cliquez les sommets sur la carte, double-cliquez pour fermer le polygone.",
    "pays": "Pays", "pays_choisir": "Choisir un pays", "pays_indispo": "indisponible", "chargement": "Chargement…",
    "pays_absent": "Liste des pays indisponible. Placez le fichier Natural Earth <code>pays.geojson</code> dans <code>donnees/</code> (voir le README).",
    "de": "De", "a": "À", "aide_normale": "La normale reste calculée sur 2003–2020.",
    "grandeur": "Grandeur affichée", "m_niveau": "Nombre de points chauds", "m_anomalie": "Écart à la normale",
    "unite": "Unité", "u_modis": "Équivalent MODIS", "u_viirs": "Équivalent VIIRS (S-NPP)",
    "aide_unite": "Même série, exprimée dans l'échelle d'un capteur. L'écart à la normale ne dépend pas de l'unité.",
    "afficher": "Afficher le calendrier",
    "b_csv": "Calendrier CSV", "b_cellules": "Cellules × mois CSV",
    "resultats": "Résultats", "o_calendrier": "Calendrier", "o_analyses": "Analyses", "o_capteurs": "Capteurs", "o_methode": "Méthode",
    "copier": "Copier le lien", "copie": "Lien copié ✓", "copier_titre": "Copier le lien de cette recherche",
    "fermer": "Fermer les résultats", "lien_prompt": "Lien de cette recherche :",
    "h_profil": "Saison type, les mois qui brûlent le plus", "h_saison": "Saison en cours comparée aux saisons passées",
    "h_annees": "Années les plus et les moins actives", "h_inhabituels": "Mois les plus inhabituels",
    "h_capteurs": "Sans harmonisation, le changement de satellite crée une fausse hausse",
    "h_validation": "VIIRS converti donne-t-il le même verdict que MODIS ?",
    "avertissement": "Un point chaud n'est pas un incendie, et l'absence de point chaud ne prouve pas l'absence de feu.",
    // couche de la carte
    "couche": "Carte du mois", "c_aucune": "Aucune couche", "c_niveau": "Points chauds", "c_anomalie": "Écart à la normale",
    "c_mois": "Mois", "c_chargement": "chargement…", "c_cellule": "cellule de 1°", "c_refus": "normale trop faible pour un écart",
    "c_aide": "Grille de 1°. Survolez une case pour sa valeur.",
    // messages
    "zone_prete": "Zone prête. Cliquez sur « Afficher le calendrier ».", "zone_incomplete": "Zone incomplète.",
    "calcul": "Calcul en cours…", "cellules_zone": n => `${n} cellules de 0,25° ayant connu au moins un point chaud.`,
    "zone_vide": " Aucune activité détectée, agrandissez la zone.",
    "poly_pret": n => `Polygone de ${n} sommets prêt.`, "poly_sommets": n => `${n} sommet(s), double-cliquez pour fermer.`,
    "d_rect": (s, n, o, e) => `emprise ${s}° à ${n}° N, ${o}° à ${e}° E`,
    "d_cercle": (r, la, lo) => `cercle de ${r} km autour de ${la}°, ${lo}°`, "d_poly": n => `polygone de ${n} sommets`,
    "u_court_modis": "équiv. MODIS", "u_court_viirs": "équiv. VIIRS",
    // indicateurs et infobulle
    "nd": "n.d.", "i_dernier": "Dernier mois disponible", "i_ecart": "Écart à la normale", "i_pic": "Mois de pic habituel",
    "i_rang": a => `Rang de ${a}`, "i_mediane_ref": "médiane 2003–2020", "x_mediane": v => `${v} × la médiane`,
    "i_total": (v, d0, d1) => `${v} points chauds sur ${d0}–${d1}`, "rang": (r, n) => `${r}e / ${n}`,
    "b_non_observe": "aucune valeur (non observé)", "b_valeur": (v, u) => `${v} points chauds (${u})`,
    "b_mediane": v => `normale du mois (médiane 2003–2020) ${v}`, "b_rapport": v => `soit ${v} fois la normale`,
    "b_source": (s, c) => `source ${s}, ${c} % des jours observés`,
    "b_ic": (a, b) => `entre ${a} et ${b} (intervalle à 95 % de la conversion)`,
    "b_frp": (v, s) => `FRP moyenne ${v} MW par détection (${s}, non harmonisée)`,
    "b_brut": (n, f) => `${n} détections brutes, multipliées en moyenne par ${f}`,
    "b_incertain": "verdict incertain", "i_ic": (a, b) => `IC 95 % ${a}–${b}`,
    "lg_incertain": "┆ verdict incertain (bord pointillé)", "g_bande": "La bande orange pâle montre l'intervalle à 95 % de la conversion.",
    // statuts, sources, refus
    "statut.mesuré": "mesuré", "statut.converti": "converti", "statut.provisoire": "provisoire",
    "statut.couverture partielle": "couverture partielle", "statut.non observé": "non observé",
    "source.VIIRS (converti)": "VIIRS (converti)", "source.MODIS provisoire": "MODIS provisoire",
    "refus.ref_insuffisante": "référence insuffisante", "refus.effectif_faible": "effectif trop faible",
    // calendrier
    "mois": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    "cal_aria": "Calendrier mensuel des points chauds harmonisés",
    "cl.tres_inf": "Très inférieure (< 0,5)", "cl.inf": "Inférieure (0,5–0,8)", "cl.normale": "Normale (0,8–1,25)",
    "cl.sup": "Supérieure (1,25–2)", "cl.tres_sup": "Très supérieure (> 2)",
    "lg_faible": "Faible", "lg_fort": "Fort", "lg_converti": "◥ converti ou provisoire",
    "lg_partiel": "▨ couverture partielle / non observé", "lg_zero": "· aucun point chaud",
    // graphiques
    "g_profil_aria": "Profil saisonnier, médiane et quartiles par mois",
    "g_profil_note": "barres pour la médiane 2003–2020, traits du 1er au 3e quartile",
    "g_saison_aria": "Saison en cours comparée aux saisons passées", "pas_donnees": "Pas de données.",
    "g_saison_note": (a, b) => `trait plein pour la saison ${a}–${b}, tirets pour la médiane, zone pour 80 % des saisons 2003–2019`,
    "g_brut_absent": "Série brute non publiée.", "g_brut_aria": "Total annuel brut et harmonisé",
    "g_bascule": "passage à VIIRS",
    "g_brut_note": "en gris les détections brutes (MODIS puis VIIRS), en orange la série harmonisée (équivalent MODIS)",
    "t_annee": "Année", "t_total": "Total", "t_rang": "Rang", "t_mois": "Mois", "t_valeur": "Valeur", "t_x_mediane": "× médiane",
    "meth.HEXAFIRE": "HEXAFIRE",
    "v_absente": "Résultats de validation non publiés.", "v_critere": "Critère", "v_cible": "Cible",
    "v.kappa": "Accord des verdicts (kappa)", "v.fausses_anomalies": "Fausses anomalies", "v.biais_median": "Biais",
    "v.erreur_mediane": "Erreur typique", "v.marche_max_annee": "Saut d'une année à l'autre",
    "v_note": "Pour chaque année testée, les facteurs sont calculés sans elle, puis VIIRS est converti cette année-là et comparé au vrai MODIS. M0 utilise VIIRS sans conversion, M1 un seul facteur pour le monde entier.",
    // export
    "x_titre": "HEXAFIRE - calendrier harmonisé des points chauds",
    "x_avert": "Un point chaud n'est pas un incendie ; l'absence de point chaud ne prouve pas l'absence de feu.",
    "x_exemple": "DONNEES D'EXEMPLE FICTIVES",
  },
  en: {
    "titre": "HEXAFIRE fire calendar",
    "sous_titre": "Harmonized MODIS + VIIRS hotspots, 2000 → today",
    "exemple": "Example data (fictitious)",
    "carte_aria": "World map where you draw or pick your area",
    "carte_absente": "Map unavailable offline. Enter coordinates in the panel.",
    "panneau_aria": "Query parameters",
    "replier": "Collapse the panel",
    "theme": "Switch theme (light / dark)",
    "langue": "Version française", "theme_sombre": "Dark theme", "theme_clair": "Light theme",
    "e1": "Choose the area", "e2": "Choose the period", "e3": "Choose the display", "e4": "Show and download",
    "z_point": "Point", "z_rect": "Box", "z_poly": "Polygon", "z_pays": "Country",
    "aide_point": "Click on the map, search a place or type coordinates (decimal degrees).",
    "lieu": "Search a place", "lieu_ph": "e.g. Parakou, Benin", "lieu_aucun": "Place not found.",
    "lieu_erreur": "Search unavailable (offline).",
    "lat": "Latitude", "lon": "Longitude", "rayon": "Radius (km)",
    "aide_rect": "Click two opposite corners on the map, or type the bounds.",
    "nord": "North", "sud": "South", "ouest": "West", "est": "East",
    "aide_poly": "Click the vertices on the map, double-click to close the polygon.",
    "pays": "Country", "pays_choisir": "Choose a country", "pays_indispo": "unavailable", "chargement": "Loading…",
    "pays_absent": "Country list unavailable. Put the Natural Earth file <code>pays.geojson</code> in <code>donnees/</code> (see the README).",
    "de": "From", "a": "To", "aide_normale": "The normal is always computed over 2003–2020.",
    "grandeur": "Displayed quantity", "m_niveau": "Number of hotspots", "m_anomalie": "Departure from normal",
    "unite": "Unit", "u_modis": "MODIS equivalent", "u_viirs": "VIIRS equivalent (S-NPP)",
    "aide_unite": "Same series, expressed on one sensor's scale. The departure from normal does not depend on the unit.",
    "afficher": "Show the calendar",
    "b_csv": "Calendar CSV", "b_cellules": "Cells × months CSV",
    "resultats": "Results", "o_calendrier": "Calendar", "o_analyses": "Analyses", "o_capteurs": "Sensors", "o_methode": "Method",
    "copier": "Copy link", "copie": "Link copied ✓", "copier_titre": "Copy the link to this query",
    "fermer": "Close results", "lien_prompt": "Link to this query:",
    "h_profil": "Typical season, the months that burn most", "h_saison": "Current season compared with past seasons",
    "h_annees": "Most and least active years", "h_inhabituels": "Most unusual months",
    "h_capteurs": "Without harmonization, the change of satellite creates a false increase",
    "h_validation": "Does converted VIIRS give the same verdict as MODIS?",
    "avertissement": "A hotspot is not a wildfire, and the absence of hotspots does not prove the absence of fire.",
    "couche": "Monthly map", "c_aucune": "No layer", "c_niveau": "Hotspots", "c_anomalie": "Departure from normal",
    "c_mois": "Month", "c_chargement": "loading…", "c_cellule": "1° cell", "c_refus": "normal too low for a departure",
    "c_aide": "1° grid. Hover a cell to read its value.",
    "zone_prete": "Area ready. Click “Show the calendar”.", "zone_incomplete": "Incomplete area.",
    "calcul": "Computing…", "cellules_zone": n => `${n} cells of 0.25° with at least one hotspot.`,
    "zone_vide": " No activity detected, enlarge the area.",
    "poly_pret": n => `Polygon with ${n} vertices ready.`, "poly_sommets": n => `${n} vertex(es), double-click to close.`,
    "d_rect": (s, n, o, e) => `bounds ${s}° to ${n}° N, ${o}° to ${e}° E`,
    "d_cercle": (r, la, lo) => `${r} km circle around ${la}°, ${lo}°`, "d_poly": n => `polygon with ${n} vertices`,
    "u_court_modis": "MODIS eq.", "u_court_viirs": "VIIRS eq.",
    "nd": "n/a", "i_dernier": "Latest month available", "i_ecart": "Departure from normal", "i_pic": "Usual peak month",
    "i_rang": a => `Rank of ${a}`, "i_mediane_ref": "2003–2020 median", "x_mediane": v => `${v} × the median`,
    "i_total": (v, d0, d1) => `${v} hotspots over ${d0}–${d1}`, "rang": (r, n) => `#${r} / ${n}`,
    "b_non_observe": "no value (not observed)", "b_valeur": (v, u) => `${v} hotspots (${u})`,
    "b_mediane": v => `normal for this month (2003–2020 median) ${v}`, "b_rapport": v => `that is ${v} times the normal`,
    "b_source": (s, c) => `source ${s}, ${c} % of days observed`,
    "b_ic": (a, b) => `between ${a} and ${b} (95% conversion interval)`,
    "b_frp": (v, s) => `mean FRP ${v} MW per detection (${s}, not harmonized)`,
    "b_brut": (n, f) => `${n} raw detections, multiplied on average by ${f}`,
    "b_incertain": "uncertain verdict", "i_ic": (a, b) => `95% CI ${a}–${b}`,
    "lg_incertain": "┆ uncertain verdict (dotted border)", "g_bande": "The pale orange band shows the 95% conversion interval.",
    "statut.mesuré": "measured", "statut.converti": "converted", "statut.provisoire": "provisional",
    "statut.couverture partielle": "partial coverage", "statut.non observé": "not observed",
    "source.VIIRS (converti)": "VIIRS (converted)", "source.MODIS provisoire": "MODIS (provisional)",
    "refus.ref_insuffisante": "insufficient reference", "refus.effectif_faible": "counts too low",
    "mois": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "cal_aria": "Monthly calendar of harmonized hotspots",
    "cl.tres_inf": "Much below (< 0.5)", "cl.inf": "Below (0.5–0.8)", "cl.normale": "Normal (0.8–1.25)",
    "cl.sup": "Above (1.25–2)", "cl.tres_sup": "Much above (> 2)",
    "lg_faible": "Low", "lg_fort": "High", "lg_converti": "◥ converted or provisional",
    "lg_partiel": "▨ partial coverage / not observed", "lg_zero": "· no hotspot",
    "g_profil_aria": "Seasonal profile: median and quartiles by month",
    "g_profil_note": "bars for the 2003–2020 median, lines from the 1st to the 3rd quartile",
    "g_saison_aria": "Current season compared with past seasons", "pas_donnees": "No data.",
    "g_saison_note": (a, b) => `solid line for season ${a}–${b}, dashed for the median, band for 80% of 2003–2019 seasons`,
    "g_brut_absent": "Raw series not published.", "g_brut_aria": "Annual raw and harmonized totals",
    "g_bascule": "switch to VIIRS",
    "g_brut_note": "raw detections in grey (MODIS then VIIRS), harmonized series in orange (MODIS equivalent)",
    "t_annee": "Year", "t_total": "Total", "t_rang": "Rank", "t_mois": "Month", "t_valeur": "Value", "t_x_mediane": "× median",
    "meth.HEXAFIRE": "HEXAFIRE", "meth.M1 facteur global": "M1 global factor", "meth.M0 raccord brut": "M0 raw splice",
    "v_absente": "Validation results not published.", "v_critere": "Criterion", "v_cible": "Target",
    "v.kappa": "Verdict agreement (kappa)", "v.fausses_anomalies": "False anomalies", "v.biais_median": "Bias",
    "v.erreur_mediane": "Typical error", "v.marche_max_annee": "Year-to-year step",
    "v_note": "For each test year, factors are fitted without it, then VIIRS is converted for that year and compared with real MODIS. M0 uses VIIRS without conversion, M1 a single worldwide factor.",
    "x_titre": "HEXAFIRE - harmonized hotspot calendar",
    "x_avert": "A hotspot is not a wildfire; the absence of hotspots does not prove the absence of fire.",
    "x_exemple": "FICTITIOUS EXAMPLE DATA",
  },
};

let langue = "fr";
const ecouteurs = [];

export function getLangue() { return langue; }
export function locale() { return langue === "en" ? "en-GB" : "fr-FR"; }

export function t(cle, ...args) {
  const v = T[langue][cle] ?? T.fr[cle];
  if (v === undefined) return cle.includes(".") ? cle.slice(cle.indexOf(".") + 1) : cle;
  return typeof v === "function" ? v(...args) : v;
}

// Nombre formaté selon la langue
export function nf(x, dec = 0) {
  return new Intl.NumberFormat(locale(), { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(x);
}

export function appliquerTextes(racine = document) {
  document.documentElement.lang = langue;
  document.title = t("titre");
  racine.querySelectorAll("[data-i18n]").forEach(e => (e.textContent = t(e.dataset.i18n)));
  racine.querySelectorAll("[data-i18n-html]").forEach(e => (e.innerHTML = t(e.dataset.i18nHtml)));
  racine.querySelectorAll("[data-i18n-title]").forEach(e => (e.title = t(e.dataset.i18nTitle)));
  racine.querySelectorAll("[data-i18n-aria]").forEach(e => e.setAttribute("aria-label", t(e.dataset.i18nAria)));
  racine.querySelectorAll("[data-i18n-ph]").forEach(e => (e.placeholder = t(e.dataset.i18nPh)));
}

export function choisirLangue(l) {
  langue = l === "en" ? "en" : "fr";
  try { localStorage.setItem("hexafire-langue", langue); } catch { /* stockage indisponible */ }
  appliquerTextes();
  ecouteurs.forEach(f => f(langue));
}

export function langueInitiale() {
  try { const l = localStorage.getItem("hexafire-langue"); if (l) return l; } catch { /* ignoré */ }
  return (navigator.language || "fr").toLowerCase().startsWith("fr") ? "fr" : "en";
}

export function surChangementLangue(f) { ecouteurs.push(f); }
