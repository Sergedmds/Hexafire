// Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
// Statistiques (médiane historique, classes d'écart) et dessin du calendrier années x mois en SVG.
import { t } from "./i18n.js";

export const nomMois = k => t("mois")[k];   // k = 0..11
const NS = "http://www.w3.org/2000/svg";

// Rampe séquentielle (OrRd, lisible par les daltonismes courants) et divergente (RdBu, 5 classes)
const SEQUENTIELLE = ["#fff7ec", "#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#ef6548", "#d7301f", "#990000"];
export const CLASSES = [
  { cle: "tres_inf", couleur: "#2166ac", max: 0.5 },
  { cle: "inf", couleur: "#92c5de", max: 0.8 },
  { cle: "normale", couleur: "#ededed", max: 1.25 },
  { cle: "sup", couleur: "#f4a582", max: 2 },
  { cle: "tres_sup", couleur: "#b2182b", max: Infinity },
];
export const nomClasse = c => t("cl." + c.cle);
export const classeDe = rapport => CLASSES.find(c => rapport < c.max) || CLASSES[4];
export { SEQUENTIELLE };
const OBSERVE = new Set(["mesuré", "converti", "provisoire"]);

// valeursSeuil : série équivalent MODIS, sur laquelle s'applique le seuil « médiane >= 5 », pour que le même
// mois soit accepté ou refusé quelle que soit l'unité affichée.
export function statistiques(index, valeurs, valeursSeuil = valeurs, ecartsTypes = null, brut = null, frp = null) {
  const [r0, r1] = index.periode_reference;
  const parMois = Array.from({ length: 12 }, () => []), parMoisSeuil = Array.from({ length: 12 }, () => []);
  index.mois.forEach((m, t) => {
    if (OBSERVE.has(m.statut) && m.annee >= r0 && m.annee <= r1) {
      parMois[m.mois - 1].push(valeurs[t]); parMoisSeuil[m.mois - 1].push(valeursSeuil[t]);
    }
  });
  const medSeuil = parMoisSeuil.map(v => quantile(v, 0.5));
  const mediane = parMois.map(v => quantile(v, 0.5));
  const moyenne = parMois.map(v => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN));
  const q1 = parMois.map(v => quantile(v, 0.25)), q3 = parMois.map(v => quantile(v, 0.75));
  const cases = index.mois.map((m, t) => {
    const v = OBSERVE.has(m.statut) || m.statut === "couverture partielle" ? valeurs[t] : null;
    const k = m.mois - 1, med = mediane[k], nRef = parMois[k].length;
    let rapport = null, classe = null, refus = null;
    if (v !== null) {
      if (nRef < 10) refus = "ref_insuffisante";
      else if (!(medSeuil[k] >= 5)) refus = "effectif_faible";
      else { rapport = v / med; classe = classeDe(rapport); }
    }
    const rang = v === null ? null : parMois[k].filter(x => x < v).length / Math.max(nRef, 1);
    // intervalle à 95 % dû à la conversion (échelle log : v x exp(+-1,96 sd / v))
    let bas = null, haut = null, incertain = false;
    const sd = ecartsTypes ? ecartsTypes[t] : 0;
    if (v !== null && v > 0 && sd > 0) {
      const r = 1.96 * sd / v;
      bas = v * Math.exp(-r); haut = v * Math.exp(r);
      if (rapport !== null) incertain = classeDe(bas / med) !== classeDe(haut / med);
    }
    return { ...m, t, valeur: v, mediane: med, moyenne: moyenne[k], rapport, classe, refus, rang,
             bas, haut, incertain, brut: brut && v !== null ? brut[t] : null,
             frpMoy: frp && brut && v !== null && brut[t] > 0 ? frp[t] / brut[t] : null };
  });
  return { cases, mediane, moyenne, q1, q3 };
}

function quantile(v, q) {
  if (!v.length) return NaN;
  const s = [...v].sort((a, b) => a - b), p = (s.length - 1) * q, i = Math.floor(p);
  return s[i] + (s[Math.min(i + 1, s.length - 1)] - s[i]) * (p - i);
}

export function couleurNiveau(v, max) {
  if (v <= 0) return SEQUENTIELLE[0];
  const x = Math.log1p(v) / Math.log1p(max);           // échelle logarithmique
  return SEQUENTIELLE[Math.min(SEQUENTIELLE.length - 1, 1 + Math.floor(x * (SEQUENTIELLE.length - 1)))];
}

function el(nom, attrs = {}, parent) {
  const e = document.createElementNS(NS, nom);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

// Dessine le calendrier ; renvoie l'élément SVG (utilisé aussi pour l'export d'image).
export function dessiner(conteneur, stats, mode, survol, periode = null) {
  const cases = periode ? stats.cases.filter(c => c.annee >= periode[0] && c.annee <= periode[1]) : stats.cases;
  const annees = [...new Set(cases.map(c => c.annee))].sort((a, b) => b - a);   // année récente en haut
  const L = 34, H = 18, G = 2, X0 = 46, Y0 = 22;
  const w = X0 + 12 * (L + G) + 10, h = Y0 + annees.length * (H + G) + 6;
  const max = Math.max(1, ...cases.filter(c => c.valeur !== null).map(c => c.valeur));
  conteneur.innerHTML = "";
  const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, role: "img",
    "aria-label": t("cal_aria"), xmlns: NS });
  conteneur.appendChild(svg);
  const defs = el("defs", {}, svg);
  const motif = el("pattern", { id: "hachure", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: "#8a8a8a", "stroke-width": 1.2 }, motif);
  el("rect", { width: w, height: h, fill: "#ffffff", class: "fond-svg" }, svg);
  t("mois").forEach((m, k) => {
    const t = el("text", { x: X0 + k * (L + G) + L / 2, y: 14, "text-anchor": "middle" }, svg); t.textContent = m;
  });
  annees.forEach((a, i) => {
    const t = el("text", { x: X0 - 6, y: Y0 + i * (H + G) + H - 5, "text-anchor": "end" }, svg); t.textContent = a;
  });
  for (const c of cases) {
    const x = X0 + (c.mois - 1) * (L + G), y = Y0 + annees.indexOf(c.annee) * (H + G);
    let fill = "none";
    if (c.valeur !== null) {
      if (mode === "anomalie") fill = c.classe ? c.classe.couleur : "#f7f7f7";
      else fill = couleurNiveau(c.valeur, max);
    }
    const g = el("g", { "data-t": c.t }, svg);
    el("rect", { x, y, width: L, height: H, fill, stroke: c.statut === "non observé" ? "#9a9a9a" : "#ffffff",
      class: c.statut === "non observé" ? "" : "sep-svg", "stroke-dasharray": c.statut === "non observé" ? "3 2" : "none" }, g);
    if (c.statut === "couverture partielle" || c.statut === "non observé")
      el("rect", { x, y, width: L, height: H, fill: "url(#hachure)", opacity: 0.8 }, g);
    if (c.statut === "converti" || c.statut === "provisoire")
      el("path", { d: `M${x + L - 7} ${y} L${x + L} ${y} L${x + L} ${y + 7} Z`, fill: "#3b3b3b", opacity: 0.55 }, g);
    if (c.valeur === 0)
      el("circle", { cx: x + L / 2, cy: y + H / 2, r: 1.6, fill: "#9a9a9a" }, g);
    if (mode === "anomalie" && c.incertain)
      el("rect", { x: x + 1.5, y: y + 1.5, width: L - 3, height: H - 3, fill: "none", stroke: "#333",
        "stroke-width": 1, "stroke-dasharray": "2 2" }, g);
    if (mode === "anomalie" && c.valeur !== null && c.refus)
      el("rect", { x, y, width: L, height: H, fill: "#ffffff", class: "fond-svg", opacity: 0.6 }, g);
    g.addEventListener("mousemove", ev => survol(c, ev));
    g.addEventListener("mouseleave", () => survol(null));
  }
  return svg;
}

export function dessinerLegende(conteneur, mode) {
  const morceaux = [];
  if (mode === "anomalie") {
    for (const c of CLASSES) morceaux.push(`<span><i class="pastille" style="background:${c.couleur}"></i>${nomClasse(c)}</span>`);
  } else {
    morceaux.push(`<span>${t("lg_faible")} <i class="pastille" style="background:linear-gradient(90deg,${SEQUENTIELLE.join(",")});width:90px"></i> ${t("lg_fort")}</span>`);
  }
  morceaux.push(`<span>${t("lg_converti")}</span><span>${t("lg_partiel")}</span><span>${t("lg_zero")}</span>`);
  if (mode === "anomalie") morceaux.push(`<span>${t("lg_incertain")}</span>`);
  conteneur.innerHTML = morceaux.join("");
}
