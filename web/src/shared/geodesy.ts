/**
 * Géodésie martienne (C1). Toute distance ou échelle se calcule ici,
 * jamais avec MapLibre ou Turf (règle R3).
 *
 * Les résultats sont identiques à ceux de ``marswalk_core.geodesy`` (Python).
 *
 * Références :
 * - IAU_2015:49900 — sphère Mars 2000, rayon 3 396 190 m.
 * - Règle R1 : calcul en mètres dans le système d'analyse du site (eqc martien).
 * - Règle R2 : échanges en degrés Est, [−180, 180].
 * - Règle R3 : barre d'échelle et distances via ce module, jamais via MapLibre.
 */

export const MARS_2000_RADIUS_M = 3_396_190;
export const MARS_MEAN_RADIUS_M = 3_389_500;

export type LonLat = [number, number];

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

// ---------------------------------------------------------------------------
// Distances et caps
// ---------------------------------------------------------------------------

/** Distance orthodromique en mètres sur la sphère Mars 2000 (haversine). */
export function distanceM(a: LonLat, b: LonLat): number {
  const [lon1, lat1, lon2, lat2] = [rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])];
  const h =
    Math.sin((lat2 - lat1) / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 2 * MARS_2000_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Cap initial de a vers b, en degrés depuis le nord, [0, 360). */
export function bearingDeg(a: LonLat, b: LonLat): number {
  const [lon1, lat1, lon2, lat2] = [rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])];
  const x = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const y =
    Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
  return (deg(Math.atan2(x, y)) + 360) % 360;
}

// ---------------------------------------------------------------------------
// Résolution de la carte (tuiles WebMercatorQuad appliquées à Mars)
// ---------------------------------------------------------------------------

/**
 * Mètres martiens par pixel au zoom z et à la latitude lat.
 *
 * Les tuiles WebMercatorQuad sont appliquées aux coordonnées martiennes (règle R3).
 * À l'équateur, zoom z : (2π R cos lat) / (256 × 2^z).
 */
export function metersPerPixel(zoom: number, lat: number): number {
  return (2 * Math.PI * MARS_2000_RADIUS_M * Math.cos(rad(lat))) / (256 * 2 ** zoom);
}

// ---------------------------------------------------------------------------
// Barre d'échelle martienne (logique pure, sans React)
// ---------------------------------------------------------------------------

/** Paliers de distances affichables (mètres), du plus petit au plus grand. */
const SCALE_STEPS_M = [
  10, 20, 50, 100, 200, 500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000,
] as const;

/** Formate une distance en mètres : « 500 m » ou « 2 km ». */
export function formatMarsDistance(m: number): string {
  if (m >= 1_000) return `${m / 1_000} km`;
  return `${m} m`;
}

export interface ScaleBarResult {
  /** Largeur de la barre en pixels entiers. */
  widthPx: number;
  /** Label lisible : « 500 m », « 2 km »… */
  label: string;
  /** Distance réelle représentée, en mètres. */
  distanceM: number;
}

/**
 * Calcule les dimensions d'une barre d'échelle martienne.
 *
 * Choisit le plus grand palier rond dont la largeur en pixels est ≤ maxWidthPx,
 * en utilisant le rayon martien (jamais MapLibre). La valeur retournée est
 * utilisable dans n'importe quel contexte de rendu (SVG, canvas, React).
 *
 * Note : le composant React ``<MarsScaleBar>`` sera fourni dans
 * ``geodesy-scale-bar.tsx`` dès l'acceptation de la demande de changement
 * ``tasks/change-requests/C1-ownership-geodesy-tsx.md`` (l'ownership.yaml de C1
 * ne couvre pas encore les ``.tsx``).
 *
 * @param zoom       Niveau de zoom MapLibre.
 * @param lat        Latitude du centre de la vue (degrés, Mars 2000).
 * @param maxWidthPx Largeur maximale en pixels (défaut : 200).
 */
export function computeScaleBar(zoom: number, lat: number, maxWidthPx = 200): ScaleBarResult {
  const mpp = metersPerPixel(zoom, lat);
  let chosen: number = SCALE_STEPS_M[0];
  for (const step of SCALE_STEPS_M) {
    if (step / mpp <= maxWidthPx) chosen = step;
    else break;
  }
  return {
    widthPx: Math.round(chosen / mpp),
    label: formatMarsDistance(chosen),
    distanceM: chosen,
  };
}
