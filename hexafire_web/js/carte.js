// Code written with the help of Claude (Anthropic), a Super Intelligence (SI) assistant, then run and tested by team HEXAFIRE.
// Carte MapLibre plein écran : choix d'un point, rectangle (2 clics), polygone (clics + double-clic),
// couche mensuelle (points chauds ou écart à la normale) sur une grille de 1°, fond clair ou sombre.
// Sans connexion (MapLibre non chargé), l'application reste utilisable par saisie des coordonnées.

const STYLE = {
  version: 8,
  sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256,
                    attribution: "© OpenStreetMap" } },
  layers: [{ id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.6 } }],
};

function cercleAnneau(z) {
  const a = [];
  for (let i = 0; i <= 64; i++) {
    const t = (i / 64) * 2 * Math.PI;
    a.push([z.lon + (z.rayon / (111.2 * Math.cos(z.lat * Math.PI / 180))) * Math.cos(t), z.lat + (z.rayon / 111.2) * Math.sin(t)]);
  }
  return [a];
}

export function geometrie(zone) {
  if (zone.type === "rect") return [[[zone.ouest, zone.sud], [zone.est, zone.sud], [zone.est, zone.nord], [zone.ouest, zone.nord], [zone.ouest, zone.sud]]];
  if (zone.type === "cercle") return cercleAnneau(zone);
  return zone.anneaux;
}

// Peinture du fond OSM : en thème sombre, la luminosité est inversée (min > max) et la couleur retirée.
const FOND = {
  clair: { "raster-saturation": -0.6, "raster-brightness-min": 0, "raster-brightness-max": 1 },
  sombre: { "raster-saturation": -1, "raster-brightness-min": 0.92, "raster-brightness-max": 0.08 },
};

function carre(lat, lon, pas) {
  const h = pas / 2;
  return [[[lon - h, lat - h], [lon + h, lat - h], [lon + h, lat + h], [lon - h, lat + h], [lon - h, lat - h]]];
}

export function creerCarte(idConteneur, surZone, surSommets, surSurvolCouche = () => {}) {
  if (!window.maplibregl) return null;
  const carte = new maplibregl.Map({ container: idConteneur, style: STYLE, center: [10, 8], zoom: 2.4 });
  carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
  carte.addControl(new maplibregl.GeolocateControl({}), "bottom-right");
  let mode = "cercle", premier = null, sommets = [], charge = false;
  const attente = [];

  carte.on("load", () => {
    carte.addSource("couche", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    carte.addLayer({ id: "couche-fond", type: "fill", source: "couche",
      paint: { "fill-color": ["get", "couleur"], "fill-opacity": 0.78, "fill-outline-color": "rgba(0,0,0,0)" } });
    carte.addSource("zone", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    carte.addLayer({ id: "zone-fond", type: "fill", source: "zone", paint: { "fill-color": "#b4541a", "fill-opacity": 0.15 } });
    carte.addLayer({ id: "zone-bord", type: "line", source: "zone", paint: { "line-color": "#b4541a", "line-width": 2 } });
    charge = true;
    attente.splice(0).forEach(f => f());
  });

  const brouillon = coords => {
    const src = carte.getSource("zone");
    if (src) src.setData({ type: "Feature", geometry: { type: "LineString", coordinates: coords } });
  };

  carte.on("click", e => {
    const { lat, lng } = e.lngLat;
    if (mode === "cercle") surZone({ type: "point", lat, lon: lng });
    else if (mode === "rect") {
      if (!premier) { premier = [lat, lng]; brouillon([[lng, lat], [lng, lat]]); return; }
      const z = { type: "rect", sud: Math.min(premier[0], lat), nord: Math.max(premier[0], lat),
                  ouest: Math.min(premier[1], lng), est: Math.max(premier[1], lng) };
      premier = null; surZone(z);
    } else if (mode === "poly") {
      sommets.push([lng, lat]); brouillon(sommets); surSommets(sommets.length);
    }
  });
  carte.on("dblclick", e => {
    if (mode !== "poly") return;
    e.preventDefault();
    if (sommets.length >= 3) { const a = [...sommets, sommets[0]]; sommets = []; surSommets(0); surZone({ type: "poly", anneaux: [a] }); }
  });

  carte.on("mousemove", "couche-fond", e => {
    const f = e.features && e.features[0];
    surSurvolCouche(f ? f.properties : null, e.originalEvent);
  });
  carte.on("mouseleave", "couche-fond", () => surSurvolCouche(null));

  const pret = f => (charge ? f() : attente.push(f));

  return {
    // cellules : [{lat, lon, couleur, ...propriétés}] ; pas : taille des cases en degrés
    couche(cellules, pas) {
      pret(() => carte.getSource("couche").setData({ type: "FeatureCollection", features: cellules.map(c => ({
        type: "Feature", properties: c, geometry: { type: "Polygon", coordinates: carre(c.lat, c.lon, pas) } })) }));
    },
    theme(sombre) {
      pret(() => { for (const [k, v] of Object.entries(sombre ? FOND.sombre : FOND.clair)) carte.setPaintProperty("osm", k, v); });
    },
    centrer(lat, lon, zoom = 7) { carte.flyTo({ center: [lon, lat], zoom, duration: 800 }); },
    activer(m) {
      mode = m; premier = null; sommets = [];
      carte.getCanvas().style.cursor = m === "pays" ? "" : "crosshair";
      if (m === "poly") carte.doubleClickZoom.disable(); else carte.doubleClickZoom.enable();
    },
    afficher(zone) {
      if (!charge) { attente.push(() => this.afficher(zone)); return; }
      const src = carte.getSource("zone");
      const coords = geometrie(zone);
      src.setData({ type: "Feature", geometry: { type: "Polygon", coordinates: coords } });
      const pts = coords.flat(), lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
      carte.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        { padding: { top: 60, bottom: 40, left: 380, right: 40 }, maxZoom: 7, duration: 600 });
    },
  };
}
