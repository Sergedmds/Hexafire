// Petits graphiques SVG sans bibliothèque : profil saisonnier, saison cumulée, brut vs harmonisé, tableaux.
import { nomMois } from "./calendrier.js";
import { t, nf } from "./i18n.js";

const NS = "http://www.w3.org/2000/svg";

function el(nom, attrs = {}, parent) {
  const e = document.createElementNS(NS, nom);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
function texte(parent, x, y, t, attrs = {}) { const e = el("text", { x, y, ...attrs }, parent); e.textContent = t; return e; }
function svgBase(conteneur, w, h, titre) {
  conteneur.innerHTML = "";
  const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: "100%", role: "img", "aria-label": titre });
  conteneur.appendChild(s);
  return s;
}
function axeY(s, x0, y0, y1, max, n = 4) {
  for (let i = 0; i <= n; i++) {
    const v = (max * i) / n, y = y1 - ((y1 - y0) * i) / n;
    el("line", { x1: x0, x2: "100%", y1: y, y2: y, stroke: "#eee", class: "grille-svg" }, s);
    texte(s, x0 - 4, y + 4, nf(v), { "text-anchor": "end" });
  }
}

export function profilSaisonnier(conteneur, stats) {
  const W = 700, H = 220, x0 = 48, y0 = 12, y1 = H - 26, L = (W - x0 - 10) / 12;
  const max = Math.max(1, ...stats.q3.filter(Number.isFinite));
  const s = svgBase(conteneur, W, H, t("g_profil_aria"));
  axeY(s, x0, y0, y1, max);
  const Y = v => y1 - ((y1 - y0) * v) / max;
  const pic = stats.mediane.indexOf(Math.max(...stats.mediane.filter(Number.isFinite)));
  stats.mediane.forEach((m, k) => {
    if (!Number.isFinite(m)) return;
    const x = x0 + k * L + 6;
    el("rect", { x, y: Y(m), width: L - 12, height: y1 - Y(m), fill: k === pic ? "#b4541a" : "#e3a774" }, s);
    el("line", { x1: x + (L - 12) / 2, x2: x + (L - 12) / 2, y1: Y(stats.q1[k]), y2: Y(stats.q3[k]), stroke: "#3b3b3b", "stroke-width": 1.5 }, s);
    texte(s, x + (L - 12) / 2, H - 8, nomMois(k), { "text-anchor": "middle" });
  });
  texte(s, x0, 10, t("g_profil_note"), { "font-size": 10 });
}

export function saisonCumulee(conteneur, stats) {
  const cases = stats.cases.filter(c => c.valeur !== null);
  if (!cases.length) { conteneur.textContent = t("pas_donnees"); return; }
  const k0 = (stats.mediane.indexOf(Math.min(...stats.mediane.map(x => (Number.isFinite(x) ? x : Infinity)))) + 1) % 12;
  // saisons : de k0 (mois 0-11) au mois précédent l'année suivante
  const saisons = new Map();
  for (const c of cases) {
    const k = c.mois - 1, an = k >= k0 ? c.annee : c.annee - 1;
    if (!saisons.has(an)) saisons.set(an, new Array(12).fill(null));
    saisons.get(an)[(k - k0 + 12) % 12] = c.valeur;
  }
  const cumul = arr => { let s = 0; return arr.map(v => (v === null ? null : (s += v))); };
  const ref = [...saisons].filter(([a, v]) => a >= 2003 && a <= 2019 && v.every(x => x !== null)).map(([, v]) => cumul(v));
  const ans = [...saisons.keys()].sort((a, b) => a - b), enCours = ans[ans.length - 1];
  const courant = cumul(saisons.get(enCours));
  const q = (arr, p) => { const s = [...arr].sort((a, b) => a - b); const i = (s.length - 1) * p, f = Math.floor(i); return s[f] + (s[Math.min(f + 1, s.length - 1)] - s[f]) * (i - f); };
  const med = [], p10 = [], p90 = [];
  for (let i = 0; i < 12; i++) { const col = ref.map(r => r[i]); med.push(q(col, .5)); p10.push(q(col, .1)); p90.push(q(col, .9)); }
  const W = 700, H = 230, x0 = 56, y0 = 12, y1 = H - 26, L = (W - x0 - 20) / 11;
  const max = Math.max(1, ...p90.filter(Number.isFinite), ...courant.filter(v => v !== null));
  const s = svgBase(conteneur, W, H, t("g_saison_aria"));
  axeY(s, x0, y0, y1, max);
  const X = i => x0 + i * L, Y = v => y1 - ((y1 - y0) * v) / max;
  if (ref.length) {
    const haut = p90.map((v, i) => `${X(i)},${Y(v)}`), bas = p10.map((v, i) => `${X(i)},${Y(v)}`).reverse();
    el("polygon", { points: haut.concat(bas).join(" "), fill: "#e3a77455" }, s);
    el("polyline", { points: med.map((v, i) => `${X(i)},${Y(v)}`).join(" "), fill: "none", stroke: "#8a5a35", "stroke-dasharray": "5 3", "stroke-width": 1.5 }, s);
  }
  const pts = courant.map((v, i) => (v === null ? null : `${X(i)},${Y(v)}`)).filter(Boolean);
  el("polyline", { points: pts.join(" "), fill: "none", stroke: "#b4541a", "stroke-width": 2.5 }, s);
  for (let i = 0; i < 12; i++) texte(s, X(i), H - 8, nomMois((k0 + i) % 12), { "text-anchor": "middle" });
  texte(s, x0, 10, t("g_saison_note", enCours, enCours + 1), { "font-size": 10 });
}

export function brutHarmonise(conteneur, index, serie) {
  const parAn = new Map();
  index.mois.forEach((m, t) => {
    if (!parAn.has(m.annee)) parAn.set(m.annee, { v: 0, b: 0, n: 0 });
    const a = parAn.get(m.annee); a.v += serie.valeurs[t]; a.b += serie.brut[t]; a.n++;
    a.sd = (a.sd || 0) + (serie.sdModis ? serie.sdModis[t] : 0);   // somme : prudent (mois corrélés)
  });
  const ans = [...parAn].filter(([, a]) => a.n === 12).map(([an]) => an);
  if (!ans.length || ans.every(a => !Number.isFinite(parAn.get(a).b))) { conteneur.textContent = t("g_brut_absent"); return; }
  const W = 700, H = 240, x0 = 64, y0 = 14, y1 = H - 26, L = (W - x0 - 20) / Math.max(ans.length - 1, 1);
  const max = Math.max(1, ...ans.map(a => Math.max(parAn.get(a).v, parAn.get(a).b)));
  const s = svgBase(conteneur, W, H, t("g_brut_aria"));
  axeY(s, x0, y0, y1, max);
  const X = i => x0 + i * L, Y = v => y1 - ((y1 - y0) * v) / max;
  const iB = ans.findIndex(a => a >= 2021);
  if (iB > 0) {
    el("line", { x1: X(iB) - L / 2, x2: X(iB) - L / 2, y1: y0, y2: y1, stroke: "#999", "stroke-dasharray": "4 3" }, s);
    texte(s, X(iB) - L / 2 + 4, y0 + 10, t("g_bascule"), { "font-size": 10 });
  }
  el("polyline", { points: ans.map((a, i) => `${X(i)},${Y(parAn.get(a).b)}`).join(" "), fill: "none", stroke: "#8a8a8a", "stroke-width": 2 }, s);
  if (serie.sdModis) {
    const lim = (a, signe) => { const p = parAn.get(a); return p.v > 0 ? p.v * Math.exp(signe * 1.96 * p.sd / p.v) : 0; };
    const haut = ans.map((a, i) => `${X(i)},${Y(Math.min(lim(a, 1), max))}`);
    const bas = ans.map((a, i) => `${X(i)},${Y(lim(a, -1))}`).reverse();
    el("polygon", { points: haut.concat(bas).join(" "), fill: "#b4541a", "fill-opacity": 0.22, stroke: "none" }, s);
  }
  el("polyline", { points: ans.map((a, i) => `${X(i)},${Y(parAn.get(a).v)}`).join(" "), fill: "none", stroke: "#b4541a", "stroke-width": 2.5 }, s);
  ans.forEach((a, i) => { if (a % 5 === 0) texte(s, X(i), H - 8, a, { "text-anchor": "middle" }); });
  texte(s, x0, 10, t("g_brut_note"), { "font-size": 10 });
  if (serie.sdModis) {
    const n = Object.assign(document.createElement("p"), { className: "aide", textContent: t("g_bande") });
    conteneur.appendChild(n);
  }
}

export function tableAnnees(conteneur, stats) {
  const parAn = new Map();
  for (const c of stats.cases) if (c.valeur !== null) {
    const a = parAn.get(c.annee) || { s: 0, n: 0 }; a.s += c.valeur; a.n++; parAn.set(c.annee, a);
  }
  const l = [...parAn].filter(([, a]) => a.n === 12).map(([an, a]) => [an, a.s]).sort((a, b) => b[1] - a[1]);
  const ligne = ([an, s], i) => `<tr><td>${an}</td><td class="num">${nf(s)}</td><td class="num">${i}</td></tr>`;
  const haut = l.slice(0, 5).map((x, i) => ligne(x, i + 1)), bas = l.slice(-5).map((x, i) => ligne(x, l.length - 4 + i));
  conteneur.innerHTML = `<table><thead><tr><th>${t("t_annee")}</th><th class="num">${t("t_total")}</th><th class="num">${t("t_rang")}</th></tr></thead>
    <tbody>${haut.join("")}<tr><td colspan="3">…</td></tr>${bas.join("")}</tbody></table>`;
}

export function tableInhabituels(conteneur, stats) {
  const l = stats.cases.filter(c => c.rapport !== null && c.rapport > 0)
    .sort((a, b) => Math.abs(Math.log(b.rapport)) - Math.abs(Math.log(a.rapport))).slice(0, 8);
  conteneur.innerHTML = `<table><thead><tr><th>${t("t_mois")}</th><th class="num">${t("t_valeur")}</th><th class="num">${t("t_x_mediane")}</th></tr></thead><tbody>${
    l.map(c => `<tr><td>${nomMois(c.mois - 1)} ${c.annee}</td><td class="num">${nf(c.valeur)}</td>
      <td class="num">${nf(c.rapport, 2)}</td></tr>`).join("")}</tbody></table>`;
}

export function tableValidation(conteneur, validation) {
  if (!validation || !validation.length) { conteneur.textContent = t("v_absente"); return; }
  const cibles = { kappa: [v => v >= 0.5, `≥ ${nf(0.5, 1)}`], fausses_anomalies: [v => v <= 0.15, `≤ ${nf(0.15, 2)}`],
    biais_median: [v => Math.abs(v) < 0.1, `|·| < ${nf(0.1, 2)}`], erreur_mediane: [v => v < 0.25, `< ${nf(0.25, 2)}`],
    marche_max_annee: [v => v < 0.1, `< ${nf(0.1, 2)}`] };
  const meth = validation.map(v => v.methode);
  const lignes = Object.keys(cibles).map(k => `<tr><td>${t("v." + k)}</td><td>${cibles[k][1]}</td>${validation.map(v => {
    const x = v[k]; const ok = cibles[k][0](x);
    return `<td class="num ${ok ? "ok" : "ko"}">${nf(x, 3)} ${ok ? "✓" : "✗"}</td>`; }).join("")}</tr>`);
  conteneur.innerHTML = `<table><thead><tr><th>${t("v_critere")}</th><th>${t("v_cible")}</th>${meth.map(m => `<th class="num">${t("meth." + m)}</th>`).join("")}</tr></thead>
    <tbody>${lignes.join("")}</tbody></table>
    <p class="aide">${t("v_note")}</p>`;
}
