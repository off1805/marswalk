/**
 * Géodésie martienne (C1). BOUCHON de T00 : formule sphérique simple.
 * Toute distance ou échelle se calcule ici, jamais avec MapLibre ou Turf (règle R3).
 * Les résultats doivent égaler ceux de marswalk_core.geodesy.
 */
export const MARS_2000_RADIUS_M = 3_396_190;
export const MARS_MEAN_RADIUS_M = 3_389_500;

export type LonLat = [number, number];

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

/** Distance orthodromique en mètres sur la sphère Mars 2000. */
export function distanceM(a: LonLat, b: LonLat): number {
  const [lon1, lat1, lon2, lat2] = [rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])];
  const h =
    Math.sin((lat2 - lat1) / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 2 * MARS_2000_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Cap initial de a vers b, en degrés depuis le nord, de 0 à 360. */
export function bearingDeg(a: LonLat, b: LonLat): number {
  const [lon1, lat1, lon2, lat2] = [rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])];
  const x = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const y =
    Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
  return (deg(Math.atan2(x, y)) + 360) % 360;
}

/** Mètres martiens par pixel au zoom z et à la latitude lat (tuiles WebMercatorQuad de 256 px). */
export function metersPerPixel(zoom: number, lat: number): number {
  return (2 * Math.PI * MARS_2000_RADIUS_M * Math.cos(rad(lat))) / (256 * 2 ** zoom);
}
