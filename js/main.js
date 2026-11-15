// Code written with the help of Claude (Anthropic), an AI assistant, then run and tested by team HEXAFIRE.
// Point d'entrée de l'application HEXAFIRE (mise en page inspirée du Data Access Viewer de NASA POWER).
import { chargerIndex, chargerPays, serieZone, getIndex, carteMois, centreCellule } from "./donnees.js";
import { statistiques, dessiner, dessinerLegende, nomMois, nomClasse, classeDe, couleurNiveau, CLASSES } from "./calendrier.js";
import { creerCarte } from "./carte.js";
import { exporterCSV, exporterSVG, exporterPNG, exporterCellules, exporterJSON } from "./export.js";
import { profilSaisonnier, saisonCumulee, brutHarmonise, tableAnnees, tableInhabituels, tableValidation } from "./graphiques.js";
import { encoder, decoder } from "./lien.js";
import { t, nf, getLangue, choisirLangue, langueInitiale, surChangementLangue } from "./i18n.js";

const $ = id => document.getElementById(id);
const etat = { typeZone: "cercle", zone: null, serie: null, stats: null, mode: "niveau", unite: "modis",
               periode: null, svg: null, onglet: "calendrier", couche: "aucune", coucheT: null };
let carte = null, pays = [], moisCarte = [];

const nombre = id => parseFloat($(id).value);
const uniteCourte = () => t(etat.unite === "viirs" ? "u_court_viirs" : "u_court_modis");
const viirsDisponible = () => !!(getIndex().unites && getIndex().unites.viirs);

// ---------------------------------------------------------------- thème
function themeSombre() {
  const th = document.documentElement.dataset.theme;
  return th ? th === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
function basculerTheme() {
  const nouveau = themeSombre() ? "light" : "dark";
  document.documentElement.dataset.theme = nouveau;
  try { localStorage.setItem("hexafire-theme", nouveau); } catch { /* stockage indisponible */ }
  if (carte) carte.theme(nouveau === "dark");
  libelleTheme();
}
function libelleTheme() { $("btn-theme").textContent = t(themeSombre() ? "theme_clair" : "theme_sombre"); }

// ---------------------------------------------------------------- étape 1 : zone
function choisirTypeZone(type) {
  etat.typeZone = type;
  document.querySelectorAll(".onglets-zone button").forEach(b => b.classList.toggle("actif", b.dataset.zone === type));
  document.querySelectorAll("[data-panneau]").forEach(p => (p.hidden = p.dataset.panneau !== type));
  if (carte) carte.activer(type);
}

function nomPays(p) { return getLangue() === "en" ? p.nom_en : p.nom_fr; }

function remplirPays() {
  if (!pays.length) {
    $("in-pays").innerHTML = `<option value="">${t("pays_indispo")}</option>`; $("pays-absent").hidden = false; return;
  }
  const v = $("in-pays").value, loc = getLangue();
  const tries = [...pays].sort((a, b) => nomPays(a).localeCompare(nomPays(b), loc));
  $("in-pays").innerHTML = `<option value="">${t("pays_choisir")}</option>` + tries.map(p => `<option value="${p.code}">${nomPays(p)}</option>`).join("");
  $("in-pays").value = v;
}

function zoneDepuisFormulaire() {
  if (etat.typeZone === "cercle") return { type: "cercle", lat: nombre("in-lat"), lon: nombre("in-lon"), rayon: nombre("in-rayon") || 150 };
  if (etat.typeZone === "rect") return { type: "rect", sud: nombre("in-sud"), nord: nombre("in-nord"), ouest: nombre("in-ouest"), est: nombre("in-est") };
  if (etat.typeZone === "pays") { const p = pays.find(x => x.code === $("in-pays").value); return p ? { type: "pays", ...p } : null; }
  return etat.zone && etat.zone.type === "poly" ? etat.zone : null;
}

function surZoneCarte(z) {
  if (z.type === "point") {
    $("in-lat").value = z.lat.toFixed(2); $("in-lon").value = z.lon.toFixed(2);
    z = { type: "cercle", lat: z.lat, lon: z.lon, rayon: nombre("in-rayon") || 150 };
  } else if (z.type === "rect") {
    $("in-sud").value = z.sud.toFixed(2); $("in-nord").value = z.nord.toFixed(2);
    $("in-ouest").value = z.ouest.toFixed(2); $("in-est").value = z.est.toFixed(2);
  } else if (z.type === "poly") {
    $("poly-etat").textContent = t("poly_pret", z.anneaux[0].length - 1);
  }
  etat.zone = z;
  if (carte) carte.afficher(z);
  $("resume-zone").textContent = t("zone_prete");
}

function decrireZone(z) {
  const f = x => nf(x, 2);
  if (z.type === "rect") return t("d_rect", f(z.sud), f(z.nord), f(z.ouest), f(z.est));
  if (z.type === "cercle") return t("d_cercle", z.rayon, f(z.lat), f(z.lon));
  if (z.type === "pays") return nomPays(z);
  return t("d_poly", z.anneaux[0].length - 1);
}

// Recherche de lieu (OpenStreetMap Nominatim, usage léger : une requête par recherche)
async function chercherLieu(ev) {
  ev.preventDefault();
  const q = $("in-lieu").value.trim();
  if (!q) return;
  $("lieu-etat").textContent = "…";
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&accept-language=${getLangue()}&q=${encodeURIComponent(q)}`);
    const l = (await r.json())[0];
    if (!l) { $("lieu-etat").textContent = t("lieu_aucun"); return; }
    $("lieu-etat").textContent = l.display_name;
    surZoneCarte({ type: "point", lat: parseFloat(l.lat), lon: parseFloat(l.lon) });
  } catch { $("lieu-etat").textContent = t("lieu_erreur"); }
}

// ---------------------------------------------------------------- étape 4 : calcul et affichage
function calculerStats() {
  const viirs = etat.unite === "viirs" && etat.serie.viirs;
  const st = statistiques(getIndex(), valeursCourantes(), etat.serie.valeurs,
                          viirs ? etat.serie.sdViirs : etat.serie.sdModis, etat.serie.brut, etat.serie.frp);
  if (viirs) {
    // Le rapport à la normale ne dépend pas de l'unité : le verdict incertain est celui de l'équivalent MODIS
    // (en VIIRS, numérateur et normale portent le même facteur, qui se simplifie).
    const sm = statistiques(getIndex(), etat.serie.valeurs, etat.serie.valeurs, etat.serie.sdModis);
    st.cases.forEach((c, i) => (c.incertain = sm.cases[i].incertain));
  }
  return st;
}

// La valeur affichée est-elle passée par un facteur de conversion ?
function convertiAffiche(c) {
  return etat.unite === "viirs" && etat.serie.viirs ? !String(c.source).startsWith("VIIRS") : c.statut === "converti";
}

function valeursCourantes() {
  return etat.unite === "viirs" && etat.serie.viirs ? etat.serie.viirs : etat.serie.valeurs;
}

async function afficher() {
  const z = zoneDepuisFormulaire();
  if (!z || [z.lat, z.sud].some(v => v !== undefined && !Number.isFinite(v))) {
    $("resume-zone").textContent = t("zone_incomplete"); return;
  }
  etat.zone = z;
  etat.periode = [parseInt($("in-debut").value, 10), parseInt($("in-fin").value, 10)].sort((a, b) => a - b);
  if (carte) carte.afficher(z);
  $("resume-zone").textContent = t("calcul");
  etat.serie = await serieZone(z);
  etat.stats = calculerStats();
  document.querySelectorAll("#panneau .boutons button").forEach(b => (b.disabled = false));
  $("resultats").hidden = false;
  history.replaceState(null, "", encoder(etat));
  rafraichir();
}

function textesResultats() {
  if (!etat.serie) return;
  const n = etat.serie.nCellules;
  $("resume-zone").textContent = t("cellules_zone", n) + (n === 0 ? t("zone_vide") : "");
  const unite = (getIndex().unites && getIndex().unites[etat.unite]) || getIndex().unite;
  $("titre-resultats").textContent = `${decrireZone(etat.zone)} · ${etat.periode[0]}–${etat.periode[1]} · ${etat.unite === "viirs" ? t("u_viirs") : t("u_modis")}`;
  $("titre-resultats").title = unite;
}

function rafraichir() {
  if (!etat.stats) return;
  textesResultats();
  etat.svg = dessiner($("calendrier"), etat.stats, etat.mode, survol, etat.periode);
  dessinerLegende($("legende"), etat.mode);
  indicateurs();
  if (etat.onglet === "analyses") {
    profilSaisonnier($("g-profil"), etat.stats); saisonCumulee($("g-saison"), etat.stats);
    tableAnnees($("t-annees"), etat.stats); tableInhabituels($("t-inhabituels"), etat.stats);
  }
  if (etat.onglet === "capteurs") {
    brutHarmonise($("g-capteurs"), getIndex(), etat.serie); tableValidation($("t-validation"), getIndex().validation);
  }
  if (etat.onglet === "methode") $("methode").innerHTML = METHODE[getLangue()];
}

function indicateurs() {
  const [d0, d1] = etat.periode;
  const cases = etat.stats.cases.filter(c => c.valeur !== null);
  const dernier = cases[cases.length - 1];
  const total = cases.filter(c => c.annee >= d0 && c.annee <= d1).reduce((s, c) => s + c.valeur, 0);
  const med = etat.stats.mediane.map(x => (Number.isFinite(x) ? x : -1));
  const pic = med.indexOf(Math.max(...med));
  const parAnnee = new Map();
  for (const c of cases) parAnnee.set(c.annee, (parAnnee.get(c.annee) || []).concat(c.valeur));
  const completes = [...parAnnee].filter(([, v]) => v.length === 12).map(([a, v]) => [a, v.reduce((s, x) => s + x, 0)]);
  // année évaluée : la dernière année complète de la période choisie, classée parmi toutes les années complètes
  const dansPeriode = completes.filter(([a]) => a >= d0 && a <= d1);
  const [aDer, vDer] = dansPeriode[dansPeriode.length - 1] || [null, 0];
  const rang = completes.filter(([, v]) => v > vDer).length + 1;
  const ecart = dernier && dernier.rapport !== null ? t("x_mediane", nf(dernier.rapport, 1)) : (dernier && dernier.refus ? t("refus." + dernier.refus) : t("nd"));
  $("indicateurs").innerHTML = [
    [t("i_dernier"), dernier ? nf(dernier.valeur) : t("nd"), dernier ? `${nomMois(dernier.mois - 1)} ${dernier.annee} · ${t("statut." + dernier.statut)} · ${uniteCourte()}`
      + (dernier.bas !== null ? ` · ${t("i_ic", nf(dernier.bas, dernier.haut < 10 ? 1 : 0), nf(dernier.haut, dernier.haut < 10 ? 1 : 0))}` : "") : ""],
    [t("i_ecart"), ecart, dernier && dernier.classe ? nomClasse(dernier.classe) : ""],
    [t("i_pic"), pic >= 0 && med[pic] > 0 ? nomMois(pic) : t("nd"), t("i_mediane_ref")],
    [t("i_rang", aDer ?? ""), aDer ? t("rang", rang, completes.length) : t("nd"), t("i_total", nf(total), d0, d1)],
  ].map(([l, v, c]) => `<div class="indicateur"><div class="lib">${l}</div><div class="val">${v}</div><div class="ctx">${c}</div></div>`).join("");
}

function placerBulle(html, ev) {
  const b = $("infobulle");
  if (!html) { b.hidden = true; return; }
  b.innerHTML = html;
  b.style.left = `${Math.min(ev.clientX + 12, innerWidth - 270)}px`; b.style.top = `${ev.clientY + 12}px`; b.hidden = false;
}

function survol(c, ev) {
  if (!c) { placerBulle(null); return; }
  placerBulle([`<strong>${nomMois(c.mois - 1)} ${c.annee}</strong>, ${t("statut." + c.statut)}`,
    c.valeur === null ? t("b_non_observe") : t("b_valeur", nf(c.valeur, 1), uniteCourte()),
    c.bas !== null ? t("b_ic", nf(c.bas, 1), nf(c.haut, 1)) : "",
    c.brut > 0 && c.valeur !== null && convertiAffiche(c)
      ? t("b_brut", nf(c.brut), nf(c.valeur / c.brut, 3)) : "",
    Number.isFinite(c.mediane) ? t("b_mediane", nf(c.mediane, 1)) : "",
    c.rapport !== null ? t("b_rapport", nf(c.rapport, 2)) + (c.incertain ? ` · ${t("b_incertain")}` : "")
      : (c.refus ? t("refus." + c.refus) : ""),
    c.frpMoy ? t("b_frp", nf(c.frpMoy, 1), t("source." + c.source)) : "",
    t("b_source", t("source." + c.source), Math.round(c.couverture * 100))].filter(Boolean).join("<br>"), ev);
}

function choisirOnglet(o) {
  etat.onglet = o;
  document.querySelectorAll(".onglets button").forEach(b => b.classList.toggle("actif", b.dataset.onglet === o));
  document.querySelectorAll("[data-vue]").forEach(v => (v.hidden = v.dataset.vue !== o));
  rafraichir();
}

function changerUnite(u) {
  etat.unite = u === "viirs" && viirsDisponible() ? "viirs" : "modis";
  $("in-unite").value = etat.unite;
  if (etat.serie) {
    etat.stats = calculerStats();
    history.replaceState(null, "", encoder(etat));
    rafraichir();
  }
  dessinerCouche();
}

// ---------------------------------------------------------------- couche de la carte
async function dessinerCouche() {
  const mode = etat.couche;
  $("couche-options").hidden = mode === "aucune";
  if (!carte) return;
  if (mode === "aucune") { carte.couche([], 1); return; }
  const tt = etat.coucheT, m = getIndex().mois[tt];
  $("couche-mois").textContent = `${nomMois(m.mois - 1)} ${m.annee} · ${t("statut." + m.statut)}`;
  const d = await carteMois(tt);
  if (!d || etat.coucheT !== tt || etat.couche !== mode) return;
  const pas = getIndex().carte.pas, val = etat.unite === "viirs" && d.w ? d.w : d.v;
  const max = Math.max(1, ...val);
  const cellules = [];
  for (let i = 0; i < d.c.length; i++) {
    const [lat, lon] = centreCellule(d.c[i], pas), v = val[i], r = d.r[i];
    let couleur;
    if (mode === "niveau") { if (v <= 0) continue; couleur = couleurNiveau(v, max); }
    else { if (r < 0) { if (v <= 0) continue; couleur = "#9e9e9e"; } else couleur = classeDe(r).couleur; }
    cellules.push({ lat, lon, couleur, v, r });
  }
  carte.couche(cellules, pas);
  $("couche-legende").innerHTML = mode === "anomalie"
    ? CLASSES.map(c => `<span><i style="background:${c.couleur}"></i>${nomClasse(c)}</span>`).join("") +
      `<span><i style="background:#9e9e9e"></i>${t("c_refus")}</span>`
    : `<span>${t("lg_faible")} <i style="width:80px;background:linear-gradient(90deg,#fee8c8,#fdbb84,#ef6548,#990000)"></i> ${t("lg_fort")} (max ${nf(max)})</span>`;
}

function survolCouche(p, ev) {
  if (!p) { placerBulle(null); return; }
  const m = getIndex().mois[etat.coucheT];
  placerBulle([`<strong>${nomMois(m.mois - 1)} ${m.annee}</strong>, ${t("c_cellule")} ${nf(p.lat, 1)}°, ${nf(p.lon, 1)}°`,
    t("b_valeur", nf(p.v, 1), uniteCourte()),
    p.r >= 0 ? `${t("b_rapport", nf(p.r, 2))} · ${nomClasse(classeDe(p.r))}` : t("c_refus")].join("<br>"), ev);
}

// ---------------------------------------------------------------- textes de la méthode
const METHODE = {
  fr: `
<h3>Qu'est-ce qu'un point chaud ?</h3><p>C'est un pixel d'image satellite nettement plus chaud que son voisinage, attribué à un
feu actif au moment où le satellite passe. Un point chaud n'est donc pas un incendie. Un grand feu en produit beaucoup, alors que
de nombreux petits feux, ou des feux cachés par les nuages, ne sont jamais détectés.</p>
<h3>Pourquoi harmoniser MODIS et VIIRS ?</h3><p>MODIS, à bord de Terra et Aqua depuis 2000, observe avec des pixels de 1 km.
VIIRS, à bord de Suomi NPP depuis 2012 puis de NOAA-20 et NOAA-21, descend à 375 m et voit beaucoup plus de petits feux. À nombre
de passages égal, il en détecte environ cinq fois plus de jour et quinze fois plus de nuit. Sans correction, le passage de MODIS
à VIIRS ferait croire à une forte hausse des feux qui n'a jamais eu lieu.</p>
<h3>Comment HEXAFIRE corrige-t-il ?</h3><p>De 2012 à 2020, les deux capteurs ont observé en même temps. HEXAFIRE en tire un
facteur de conversion propre à chaque région, à chaque mois de l'année, et distinct pour le jour et la nuit, en tenant compte du
nombre de passages de chaque satellite. La série est mesurée par MODIS jusqu'en 2020, puis calculée à partir de VIIRS converti.
NOAA-20 et NOAA-21 sont raccordés à Suomi NPP, qui a cessé d'observer le 2 novembre 2026.</p>
<h3>Deux unités, une seule série</h3><p>L'équivalent MODIS donne ce que Terra et Aqua auraient détecté. L'équivalent VIIRS donne
ce que Suomi NPP aurait détecté seul, avec les mêmes facteurs appliqués dans l'autre sens. Seule l'échelle change, et l'écart à
la normale reste pratiquement le même.</p>
<h3>Incertitude</h3><p>Chaque facteur est estimé avec une marge d'erreur, que HEXAFIRE propage jusqu'à la zone choisie. L'infobulle
donne l'intervalle à 95 % des mois convertis et l'onglet Capteurs le dessine en bande autour de la série. En équivalent MODIS,
cette incertitude concerne les mois VIIRS et les mois où Terra observait seul (2000–2002). En équivalent VIIRS, elle concerne les
mois MODIS. Une case à bord pointillé signale un verdict incertain, quand l'intervalle chevauche deux classes d'écart. Cette marge
couvre la conversion, pas les nuages ni les limites de la détection.</p>
<h3>Comment savoir que la conversion marche ?</h3><p>On met une année de côté, on convertit VIIRS comme si MODIS n'existait plus,
puis on vérifie que chaque mois reçoit le même verdict (bas, normal ou haut) qu'avec le vrai MODIS. Les résultats sont dans
l'onglet Capteurs.</p>
<h3>Écart à la normale</h3><p>C'est le rapport entre la valeur du mois et la médiane du même mois de 2003 à 2020. Il n'est pas
calculé s'il manque des années de référence (moins de dix) ou si la médiane est inférieure à cinq points chauds. Sur la carte, il
est calculé pour chaque case de 1°.</p>
<h3>Puissance radiative (FRP)</h3><p>L'infobulle indique la FRP moyenne par détection, en mégawatts, pour le capteur utilisé ce
mois-là. Elle n'est pas harmonisée, car MODIS et VIIRS ne mesurent pas la même puissance pour un même feu. Elle se compare donc
seulement entre mois observés par le même capteur.</p>
<h3>Sources et remerciements</h3><p>Les détections de feux sont des produits de la NASA, les archives mensuelles MCD14ML (MODIS,
collections 6 et 6.1) et VNP14IMGML, VJ114IMGML et VJ214IMGML (VIIRS 375 m, collection 2). Elles ont été téléchargées sur le
serveur de l'équipe feux de l'université du Maryland (fuoco.geog.umd.edu), et les mois les plus récents par l'API NASA FIRMS. Le
fichier DATA_SOURCES.md du dépôt détaille la provenance et les conditions d'utilisation.</p>
<p><em>We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS)
(<a href="https://www.earthdata.nasa.gov/firms" target="_blank" rel="noopener">earthdata.nasa.gov/firms</a>), part of
NASA's Earth Science Data and Information System (ESDIS).</em></p>
<p>Références principales, Giglio et al. (2016) et Schroeder et al. (2014) dans Remote Sensing of Environment. Fond de carte et
recherche de lieu © contributeurs OpenStreetMap (ODbL), frontières Natural Earth (domaine public). Les données sont fournies
en l'état.</p>`,
  en: `
<h3>What is a hotspot?</h3><p>A hotspot is a satellite image pixel clearly hotter than its surroundings, attributed to an active
fire at the time of the overpass. It is not a wildfire. A large fire produces many hotspots, while many small fires, or fires
hidden by clouds, are never detected.</p>
<h3>Why harmonize MODIS and VIIRS?</h3><p>MODIS, on Terra and Aqua since 2000, observes with 1 km pixels. VIIRS, on Suomi NPP since
2012 and then on NOAA-20 and NOAA-21, goes down to 375 m and sees many more small fires. For the same number of overpasses it
detects about five times more fires by day and fifteen times more by night. Without correction, the switch from MODIS to VIIRS
would suggest a sharp rise in fires that never happened.</p>
<h3>How does HEXAFIRE correct it?</h3><p>From 2012 to 2020 both sensors observed at the same time. HEXAFIRE derives a conversion
factor for each region and each month of the year, separately for day and night, accounting for the number of overpasses of
each satellite. The series is measured by MODIS up to 2020 and computed from converted VIIRS afterwards. NOAA-20 and NOAA-21 are
linked to Suomi NPP, which stopped observing on 2 November 2026.</p>
<h3>Two units, one series</h3><p>MODIS equivalent gives what Terra and Aqua would have detected. VIIRS equivalent gives what
Suomi NPP alone would have detected, with the same factors applied the other way. Only the scale changes, and the departure from
normal stays practically the same.</p>
<h3>Uncertainty</h3><p>Each factor comes with an error margin, which HEXAFIRE propagates to the selected area. The tooltip gives
the 95% interval of converted months and the Sensors tab draws it as a band around the series. In MODIS equivalent this
uncertainty affects VIIRS months and the months when Terra observed alone (2000–2002). In VIIRS equivalent it affects MODIS
months. A cell with a dotted border marks an uncertain verdict, when the interval overlaps two departure classes. The margin
covers the conversion, not clouds or the limits of detection.</p>
<h3>How do we know the conversion works?</h3><p>We set one year aside, convert VIIRS as if MODIS no longer existed, and check that
each month gets the same verdict (low, normal or high) as with real MODIS. Results are in the Sensors tab.</p>
<h3>Departure from normal</h3><p>It is the ratio between the month's value and the median of the same month from 2003 to 2020. It
is not computed when reference years are missing (fewer than ten) or when the median is below five hotspots. On the map it is
computed for each 1° cell.</p>
<h3>Fire radiative power (FRP)</h3><p>The tooltip shows the mean FRP per detection, in megawatts, for the sensor used that month.
It is not harmonized, because MODIS and VIIRS do not measure the same power for the same fire. Compare it only between months
observed by the same sensor.</p>
<h3>Sources and acknowledgements</h3><p>Fire detections are NASA products, the monthly archives MCD14ML (MODIS, collections 6 and
6.1) and VNP14IMGML, VJ114IMGML and VJ214IMGML (VIIRS 375 m, collection 2). They were downloaded from the University of Maryland
fire team server (fuoco.geog.umd.edu), and the most recent months from the NASA FIRMS API. The file DATA_SOURCES.md in the
repository details provenance and terms of use.</p>
<p><em>We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS)
(<a href="https://www.earthdata.nasa.gov/firms" target="_blank" rel="noopener">earthdata.nasa.gov/firms</a>), part of
NASA's Earth Science Data and Information System (ESDIS).</em></p>
<p>Main references are Giglio et al. (2016) and Schroeder et al. (2014) in Remote Sensing of Environment. Base map and place
search © OpenStreetMap contributors (ODbL), borders from Natural Earth (public domain). Data are provided as is.</p>`,
};

// ---------------------------------------------------------------- démarrage
async function demarrer() {
  const lien = decoder(location.hash);
  choisirLangue((lien && lien.langue) || langueInitiale());
  $("btn-langue").textContent = getLangue() === "fr" ? "EN" : "FR";
  libelleTheme();

  let idx;
  try { idx = await chargerIndex("donnees"); }
  catch (e) { $("resume-zone").textContent = e.message; return; }
  if (idx.exemple) $("bandeau-exemple").hidden = false;
  const annees = [...new Set(idx.mois.map(m => m.annee))];
  for (const id of ["in-debut", "in-fin"]) $(id).innerHTML = annees.map(a => `<option>${a}</option>`).join("");
  $("in-debut").value = annees[0]; $("in-fin").value = annees[annees.length - 1];
  $("in-unite").querySelector('option[value="viirs"]').disabled = !viirsDisponible();
  $("methode").innerHTML = METHODE[getLangue()];

  carte = creerCarte("carte", surZoneCarte, n => ($("poly-etat").textContent = n ? t("poly_sommets", n) : ""), survolCouche);
  if (!carte) $("carte-absente").hidden = false; else carte.theme(themeSombre());

  // couche de la carte : mois observés seulement
  moisCarte = idx.carte ? idx.mois.filter(m => m.statut !== "non observé").map(m => m.t) : [];
  if (!moisCarte.length || !carte) $("boite-couche").hidden = true;
  else {
    $("in-couche-t").max = moisCarte.length - 1; $("in-couche-t").value = moisCarte.length - 1;
    etat.coucheT = moisCarte[moisCarte.length - 1];
  }

  pays = await chargerPays();
  remplirPays();
  $("in-pays").onchange = () => { const z = zoneDepuisFormulaire(); if (z) surZoneCarte(z); };

  document.querySelectorAll(".onglets-zone button").forEach(b => (b.onclick = () => choisirTypeZone(b.dataset.zone)));
  document.querySelectorAll(".onglets button").forEach(b => (b.onclick = () => choisirOnglet(b.dataset.onglet)));
  document.querySelectorAll('input[name="mode"]').forEach(r => r.addEventListener("change", () => {
    etat.mode = r.value; if (etat.serie) history.replaceState(null, "", encoder(etat)); rafraichir(); }));
  $("in-unite").onchange = () => changerUnite($("in-unite").value);
  $("form-lieu").onsubmit = chercherLieu;
  $("in-couche").onchange = () => { etat.couche = $("in-couche").value; dessinerCouche(); };
  $("in-couche-t").oninput = () => { etat.coucheT = moisCarte[+$("in-couche-t").value]; dessinerCouche(); };
  $("btn-afficher").onclick = afficher;
  $("btn-csv").onclick = () => exporterCSV(etat.stats, etat.zone, etat.unite);
  $("btn-cellules").onclick = () => exporterCellules(etat.serie, etat.zone);
  $("btn-json").onclick = () => exporterJSON(etat.stats, etat.zone, etat.unite);
  $("btn-svg").onclick = () => exporterSVG(etat.svg);
  $("btn-png").onclick = () => exporterPNG(etat.svg);
  $("btn-fermer").onclick = () => ($("resultats").hidden = true);
  $("btn-theme").onclick = basculerTheme;
  $("btn-langue").onclick = () => choisirLangue(getLangue() === "fr" ? "en" : "fr");
  $("btn-lien").onclick = async () => {
    const url = encoder(etat);
    try { await navigator.clipboard.writeText(url); $("btn-lien").textContent = t("copie"); }
    catch { prompt(t("lien_prompt"), url); }
    setTimeout(() => ($("btn-lien").textContent = t("copier")), 2000);
  };
  $("btn-replier").onclick = () => {
    const p = $("panneau"), replie = p.classList.toggle("replie");
    $("btn-replier").textContent = replie ? "▶" : "◀"; $("btn-replier").setAttribute("aria-expanded", String(!replie));
  };

  surChangementLangue(() => {
    $("btn-langue").textContent = getLangue() === "fr" ? "EN" : "FR";
    libelleTheme();
    remplirPays();
    if (etat.zone && etat.zone.type === "poly") $("poly-etat").textContent = t("poly_pret", etat.zone.anneaux[0].length - 1);
    if (etat.serie) { history.replaceState(null, "", encoder(etat)); rafraichir(); }
    else $("resume-zone").textContent = "";
    $("methode").innerHTML = METHODE[getLangue()];
    dessinerCouche();
  });

  // Lien partagé : on restaure la recherche
  if (lien && lien.zone) {
    if (lien.periode) { $("in-debut").value = lien.periode[0]; $("in-fin").value = lien.periode[1]; }
    if (lien.mode === "anomalie") { document.querySelector('input[value="anomalie"]').checked = true; etat.mode = "anomalie"; }
    if (lien.unite === "viirs" && viirsDisponible()) { etat.unite = "viirs"; $("in-unite").value = "viirs"; }
    const z = lien.zone;
    choisirTypeZone(z.type === "cercle" ? "cercle" : z.type);
    if (z.type === "cercle") { $("in-lat").value = z.lat; $("in-lon").value = z.lon; $("in-rayon").value = z.rayon; }
    if (z.type === "rect") { $("in-sud").value = z.sud; $("in-nord").value = z.nord; $("in-ouest").value = z.ouest; $("in-est").value = z.est; }
    if (z.type === "pays") $("in-pays").value = z.code;
    if (z.type === "poly") etat.zone = z;
    await afficher();
  } else {
    choisirTypeZone("cercle");
  }
}

window.addEventListener("load", demarrer);
