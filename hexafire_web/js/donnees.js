// Chargement des fichiers publiés par le moteur (format d'échange v1) et calcul de la série d'une zone.
// Types de zone : cercle {lat, lon, rayon}, rect {sud, nord, ouest, est},
//                 poly {anneaux: [[[lon, lat], ...]]}, pays {code, nom, anneaux: [...]}.

const RAYON_TERRE = 6371;
let index = null;
const cacheTuiles = new Map();

export async function chargerIndex(base = "donnees") {
  const r = await fetch(`${base}/index.json`);
  if (!r.ok) throw new Error(`index.json introuvable (${r.status}). Lancez : python -m hexafire publier --exemple`);
  index = await r.json();
  index.base = base;
  index.nMois = index.mois.length;
  index.tuilesSet = new Set(index.tuiles);
  return index;
}

export async function chargerPays() {
  try {
    const r = await fetch(`${index.base}/pays.geojson`);
    if (!r.ok) return [];
    const gj = await r.json();
    return gj.features.map(f => {
      const p = f.properties || {};
      const g = f.geometry;
      const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
      return { code: p.ISO_A3 && p.ISO_A3 !== "-99" ? p.ISO_A3 : (p.ADM0_A3 || p.NAME),
               nom_fr: p.NAME_FR || p.NAME || p.ADMIN || "?", nom_en: p.NAME_EN || p.NAME || p.ADMIN || "?",
               anneaux: polys.flat() };
    }).filter(p => p.anneaux.length);
  } catch { return []; }
}

export function centreCellule(cellule, pas = index.pas_grille) {
  const nLon = Math.round(360 / pas);
  const lig = Math.floor(cellule / nLon), col = cellule % nLon;
  return [90 - (lig + 0.5) * pas, -180 + (col + 0.5) * pas];
}

export function emprise(zone) {
  if (zone.type === "rect") return [zone.sud, zone.nord, zone.ouest, zone.est];
  if (zone.type === "cercle") {
    const dLat = zone.rayon / 111.2;
    const dLon = zone.rayon / (111.2 * Math.max(Math.cos(zone.lat * Math.PI / 180), 0.05));
    return [zone.lat - dLat, zone.lat + dLat, zone.lon - dLon, zone.lon + dLon];
  }
  let s = 90, n = -90, o = 180, e = -180;
  for (const a of zone.anneaux) for (const [x, y] of a) { s = Math.min(s, y); n = Math.max(n, y); o = Math.min(o, x); e = Math.max(e, x); }
  return [s, n, o, e];
}

function distanceKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180, dLat = (lat2 - lat1) * r, dLon = (lon2 - lon1) * r;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLon / 2) ** 2;
  return 2 * RAYON_TERRE * Math.asin(Math.sqrt(a));
}

// Lancer de rayon, règle pair-impair sur tous les anneaux (gère les trous et les multipolygones)
function dansAnneaux(anneaux, lat, lon) {
  let dedans = false;
  for (const a of anneaux) {
    for (let i = 0, j = a.length - 1; i < a.length; j = i++) {
      const [xi, yi] = a[i], [xj, yj] = a[j];
      if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) dedans = !dedans;
    }
  }
  return dedans;
}

export function dansZone(zone, lat, lon) {
  if (zone.type === "rect") return lat >= zone.sud && lat <= zone.nord && lon >= zone.ouest && lon <= zone.est;
  if (zone.type === "cercle") return distanceKm(zone.lat, zone.lon, lat, lon) <= zone.rayon;
  return dansAnneaux(zone.anneaux, lat, lon);
}

function tuilesTouchees(zone) {
  const [s, n, o, e] = emprise(zone), T = index.taille_tuile, ids = [];
  for (let i = Math.floor((s + 90) / T); i <= Math.floor((n + 90) / T); i++)
    for (let j = Math.floor((o + 180) / T); j <= Math.floor((e + 180) / T); j++) {
      const id = `${i}_${j}`;
      if (index.tuilesSet.has(id)) ids.push(id);
    }
  return ids;
}

async function tuile(id) {
  if (!cacheTuiles.has(id)) cacheTuiles.set(id, fetch(`${index.base}/tuiles/t_${id}.json`).then(r => r.json()));
  return cacheTuiles.get(id);
}

// Série mensuelle de la zone : somme des cellules dont le centre est dans la zone (règle P8).
// valeurs = harmonisé équivalent MODIS ; viirs = équivalent VIIRS (si publié) ; brut = détections brutes
// de la source du mois ; lignes = détail cellule x mois [cellule, lat, lon, t, v, b, w].
// Incertitude de conversion : dans une même strate, le même facteur s'applique à toutes les cellules (écarts types
// additionnés) ; d'une strate à l'autre, les facteurs sont estimés séparément (variances additionnées).
export async function serieZone(zone) {
  const valeurs = new Float64Array(index.nMois), brut = new Float64Array(index.nMois);
  const viirs = new Float64Array(index.nMois), frp = new Float64Array(index.nMois);
  const parStrateE = new Map(), parStrateF = new Map();
  const B = index.taille_bloc || 10, nLonB = Math.round(360 / B);
  let aViirs = true, aIncert = false;
  const cellules = new Set(), lignes = [];
  for (const id of tuilesTouchees(zone)) {
    const t = await tuile(id);
    let derniere = -1, dedans = false, lat = 0, lon = 0, strate = 0;
    for (let k = 0; k < t.cellules.length; k++) {
      const c = t.cellules[k];
      if (c !== derniere) {
        [lat, lon] = centreCellule(c);
        dedans = dansZone(zone, lat, lon);
        strate = Math.floor((90 - lat) / B) * nLonB + Math.floor((lon + 180) / B);
        derniere = c;
        if (dedans) cellules.add(c);
      }
      if (!dedans) continue;
      valeurs[t.t[k]] += t.v[k];
      const b = t.b ? t.b[k] : NaN;
      brut[t.t[k]] += b;
      const w = t.w ? t.w[k] : NaN;
      if (t.w) viirs[t.t[k]] += w; else aViirs = false;
      if (t.p) frp[t.t[k]] += t.p[k];
      if (t.e) {
        aIncert = true;
        for (const [m, x] of [[parStrateE, t.e[k]], [parStrateF, t.f[k]]]) {
          if (!m.has(strate)) m.set(strate, new Float64Array(index.nMois));
          m.get(strate)[t.t[k]] += x;
        }
      }
      lignes.push([c, lat, lon, t.t[k], t.v[k], b, w, t.p ? t.p[k] : NaN]);
    }
  }
  const combiner = m => {
    const sd = new Float64Array(index.nMois);
    for (const a of m.values()) for (let i = 0; i < sd.length; i++) sd[i] += a[i] * a[i];
    return sd.map(Math.sqrt);
  };
  return { valeurs, viirs: aViirs ? viirs : null, brut, frp, lignes, nCellules: cellules.size, emprise: emprise(zone),
           sdModis: aIncert ? combiner(parStrateE) : null, sdViirs: aIncert ? combiner(parStrateF) : null };
}

export function getIndex() { return index; }

// Couche de la carte pour le mois t : {c, v, w, r} sur une grille de index.carte.pas degrés.
const cacheCartes = new Map();
export function carteMois(t) {
  if (!index.carte) return Promise.resolve(null);
  if (!cacheCartes.has(t)) cacheCartes.set(t, fetch(`${index.base}/${index.carte.modele.replace("{t}", t)}`)
    .then(r => (r.ok ? r.json() : null)).catch(() => null));
  return cacheCartes.get(t);
}
