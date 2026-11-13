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
  etat.stats = statistiques(getIndex(), valeursCourantes(), etat.serie.valeurs);
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
  const ecart = dernier && dernier.rapport !== null ? t("x_mediane", nf(dernier.rapport, 1)) : (dernier && dernier.refus ? t("refus." + dernier.refus) : "—");
  $("indicateurs").innerHTML = [
    [t("i_dernier"), dernier ? nf(dernier.valeur) : "—", dernier ? `${nomMois(dernier.mois - 1)} ${dernier.annee} · ${t("statut." + dernier.statut)} · ${uniteCourte()}` : ""],
    [t("i_ecart"), ecart, dernier && dernier.classe ? nomClasse(dernier.classe) : ""],
    [t("i_pic"), pic >= 0 && med[pic] > 0 ? nomMois(pic) : "—", t("i_mediane_ref")],
    [t("i_rang", aDer ?? "—"), aDer ? t("rang", rang, completes.length) : "—", t("i_total", nf(total), d0, d1)],
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
  placerBulle([`<strong>${nomMois(c.mois - 1)} ${c.annee}</strong> — ${t("statut." + c.statut)}`,
    c.valeur === null ? t("b_non_observe") : t("b_valeur", nf(c.valeur, 1), uniteCourte()),
    t("b_mediane", Number.isFinite(c.mediane) ? nf(c.mediane, 1) : "—"),
    c.rapport !== null ? t("b_rapport", nf(c.rapport, 2)) : (c.refus ? t("refus." + c.refus) : ""),
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
    etat.stats = statistiques(getIndex(), valeursCourantes(), etat.serie.valeurs);
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
  placerBulle([`<strong>${nomMois(m.mois - 1)} ${m.annee}</strong> — ${t("c_cellule")} ${nf(p.lat, 1)}°, ${nf(p.lon, 1)}°`,
    t("b_valeur", nf(p.v, 1), uniteCourte()),
    p.r >= 0 ? `${t("b_rapport", nf(p.r, 2))} · ${nomClasse(classeDe(p.r))}` : t("c_refus")].join("<br>"), ev);
}

// ---------------------------------------------------------------- textes de la méthode
const METHODE = {
  fr: `
<h3>Qu'est-ce qu'un point chaud ?</h3><p>Un pixel d'image satellite nettement plus chaud que son voisinage, attribué à un feu
actif au moment du passage du satellite. Ce n'est pas un incendie : un grand feu produit de nombreux points chauds, et beaucoup de
petits feux, ou de feux masqués par les nuages, ne sont jamais détectés.</p>
<h3>Pourquoi harmoniser MODIS et VIIRS ?</h3><p>MODIS (satellites Terra et Aqua, depuis 2000) a des pixels de 1 km. VIIRS
(Suomi NPP depuis 2012, NOAA-20, NOAA-21) a des pixels de 375 m et voit beaucoup plus de petits feux : à nombre de passages égal,
environ 5 fois plus de jour et 15 fois plus de nuit. Sans correction, le passage de MODIS à VIIRS crée une fausse hausse.</p>
<h3>Comment ?</h3><p>Sur 2012–2020, quand les deux capteurs observaient ensemble, HEXAFIRE apprend le facteur de conversion entre eux,
par région, par mois de l'année et séparément pour le jour et la nuit, en tenant compte du nombre de passages de chaque satellite.
Les détections VIIRS sont ensuite exprimées en « équivalent MODIS ». Jusqu'en 2020 la série est mesurée par MODIS ; depuis 2021,
elle vient de VIIRS converti (S-NPP, puis NOAA-20 et NOAA-21, raccordés à S-NPP).</p>
<h3>Deux unités, une seule série</h3><p>« Équivalent MODIS » : ce que Terra et Aqua auraient détecté. « Équivalent VIIRS » :
ce que S-NPP seul aurait détecté, obtenu avec les mêmes facteurs pris dans l'autre sens. Les deux unités décrivent la même série ;
seule l'échelle change. L'écart à la normale est pratiquement le même dans les deux unités.</p>
<h3>Comment savoir que ça marche ?</h3><p>On cache une année, on convertit VIIRS comme si MODIS n'existait plus, et on vérifie
que le verdict « mois bas, normal ou haut » est le même qu'avec le vrai MODIS (onglet Capteurs).</p>
<h3>Écart à la normale</h3><p>Rapport entre la valeur du mois et la médiane du même mois sur 2003–2020. Il n'est pas calculé si
moins de 10 années de référence sont disponibles ou si la médiane est inférieure à 5 points chauds. Sur la carte, il est calculé
pour chaque case de 1°.</p>
<h3>Sources et remerciements</h3><p>Détections de feux : produits de la NASA. Archives mensuelles MCD14ML (MODIS, collections 6
et 6.1) et VNP14IMGML, VJ114IMGML, VJ214IMGML (VIIRS 375 m, collection 2), téléchargées sur le serveur de l'équipe feux de
l'université du Maryland (fuoco.geog.umd.edu) ; mois les plus récents par l'API NASA FIRMS. Détail et conditions
d'utilisation : fichier DATA_SOURCES.md du dépôt.</p>
<p><em>We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS)
(<a href="https://www.earthdata.nasa.gov/firms" target="_blank" rel="noopener">earthdata.nasa.gov/firms</a>), part of
NASA's Earth Science Data and Information System (ESDIS).</em></p>
<p>Références : Giglio et al. (2016), Remote Sensing of Environment 178 ; Schroeder et al. (2014), Remote Sensing of
Environment 143. Fond de carte et recherche de lieu : © contributeurs OpenStreetMap (ODbL). Frontières : Natural Earth
(domaine public). Données fournies « en l'état ».</p>`,
  en: `
<h3>What is a hotspot?</h3><p>A satellite image pixel clearly hotter than its surroundings, attributed to an active fire at the time
of the satellite overpass. It is not a wildfire: a large fire produces many hotspots, and many small fires, or fires hidden by
clouds, are never detected.</p>
<h3>Why harmonize MODIS and VIIRS?</h3><p>MODIS (Terra and Aqua satellites, since 2000) has 1 km pixels. VIIRS (Suomi NPP since
2012, NOAA-20, NOAA-21) has 375 m pixels and sees many more small fires: for the same number of overpasses, about 5 times more by
day and 15 times more by night. Without correction, the switch from MODIS to VIIRS creates a false increase.</p>
<h3>How?</h3><p>Over 2012–2020, while both sensors were observing, HEXAFIRE learns the conversion factor between them, by region,
by month of the year and separately for day and night, accounting for the number of overpasses of each satellite. VIIRS detections
are then expressed as “MODIS equivalent”. Up to 2020 the series is measured by MODIS; since 2021 it comes from converted VIIRS
(S-NPP, then NOAA-20 and NOAA-21, linked to S-NPP).</p>
<h3>Two units, one series</h3><p>“MODIS equivalent”: what Terra and Aqua would have detected. “VIIRS equivalent”: what S-NPP
alone would have detected, obtained with the same factors applied the other way. Both units describe the same series; only the
scale changes. The departure from normal is practically the same in both units.</p>
<h3>How do we know it works?</h3><p>We hide one year, convert VIIRS as if MODIS no longer existed, and check that the verdict
“low, normal or high month” matches the one obtained with real MODIS (Sensors tab).</p>
<h3>Departure from normal</h3><p>Ratio between the month's value and the median of the same month over 2003–2020. It is not
computed when fewer than 10 reference years are available or when the median is below 5 hotspots. On the map, it is computed for
each 1° cell.</p>
<h3>Sources and acknowledgements</h3><p>Fire detections: NASA products. Monthly archives MCD14ML (MODIS, collections 6
and 6.1) and VNP14IMGML, VJ114IMGML, VJ214IMGML (VIIRS 375 m, collection 2), downloaded from the University of Maryland
fire team server (fuoco.geog.umd.edu); most recent months from the NASA FIRMS API. Details and terms of use: file
DATA_SOURCES.md in the repository.</p>
<p><em>We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS)
(<a href="https://www.earthdata.nasa.gov/firms" target="_blank" rel="noopener">earthdata.nasa.gov/firms</a>), part of
NASA's Earth Science Data and Information System (ESDIS).</em></p>
<p>References: Giglio et al. (2016), Remote Sensing of Environment 178; Schroeder et al. (2014), Remote Sensing of
Environment 143. Base map and place search: © OpenStreetMap contributors (ODbL). Borders: Natural Earth (public domain).
Data provided “as is”.</p>`,
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
