// Lien partageable : la zone et les options sont encodées dans l'adresse (#...), comme l'URL de requête de NASA POWER.

export function encoder(etat) {
  const z = etat.zone, p = new URLSearchParams();
  if (z.type === "cercle") p.set("z", `cercle:${z.lat.toFixed(3)},${z.lon.toFixed(3)},${z.rayon}`);
  else if (z.type === "rect") p.set("z", `rect:${[z.sud, z.nord, z.ouest, z.est].map(v => v.toFixed(3)).join(",")}`);
  else if (z.type === "pays") p.set("z", `pays:${z.code}`);
  else p.set("z", `poly:${z.anneaux[0].map(([x, y]) => `${x.toFixed(3)} ${y.toFixed(3)}`).join(";")}`);
  p.set("m", etat.mode);
  p.set("a", `${etat.periode[0]}-${etat.periode[1]}`);
  if (etat.unite && etat.unite !== "modis") p.set("u", etat.unite);
  p.set("l", document.documentElement.lang || "fr");
  return `${location.origin}${location.pathname}#${p.toString()}`;
}

export function decoder(hash) {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const z = p.get("z");
  if (!z) return p.get("l") ? { zone: null, langue: p.get("l") } : null;
  const [type, v] = [z.slice(0, z.indexOf(":")), z.slice(z.indexOf(":") + 1)];
  let zone = null;
  if (type === "cercle") { const [lat, lon, rayon] = v.split(",").map(Number); zone = { type, lat, lon, rayon }; }
  else if (type === "rect") { const [sud, nord, ouest, est] = v.split(",").map(Number); zone = { type, sud, nord, ouest, est }; }
  else if (type === "pays") zone = { type, code: v };
  else if (type === "poly") zone = { type, anneaux: [v.split(";").map(s => s.split(" ").map(Number))] };
  const a = (p.get("a") || "").split("-").map(Number);
  return { zone, mode: p.get("m") || "niveau", periode: a.length === 2 && a.every(Number.isFinite) ? a : null,
           unite: p.get("u") || "modis", langue: p.get("l") };
}
