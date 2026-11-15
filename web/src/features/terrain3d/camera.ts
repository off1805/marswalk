/**
 * Camera placement for the 3D terrain (MapLibre). Pure geometry, plus thin helpers
 * that apply it to a map.
 *
 * Flyover: a chase camera a few dozen metres behind the walker and above the ground,
 * looking at a point further along the route, so climbs and descents read as such.
 */
import maplibregl from "maplibre-gl";
import { sampleProfile, type RouteProfile } from "./flyover";

/** Distance behind the walker, height above the ground and look-ahead of the chase camera. */
export const CHASE = { backM: 70, heightM: 28, aheadM: 90 } as const;

const MARS_RADIUS_M = 3_389_500;
const M_PER_DEG_LAT = MARS_RADIUS_M * (Math.PI / 180);

/**
 * MapLibre measures the ground with the Earth's radius. On Martian degrees its
 * horizontal metres are 1.88 times too long, so heights must be scaled by the same
 * factor to keep the true proportions (×1 exaggeration = real slopes).
 */
export const MARS_TO_RENDER = 6_371_008.8 / MARS_RADIUS_M;

/** Initial bearing (degrees from north) of the route at a distance. */
export function bearingAt(profile: RouteProfile[], distanceM: number): number {
  const a = sampleProfile(profile, Math.max(0, distanceM - 15)).position;
  const b = sampleProfile(profile, distanceM + 15).position;
  const dx = (b[0] - a[0]) * Math.cos((a[1] * Math.PI) / 180);
  const dy = b[1] - a[1];
  if (dx === 0 && dy === 0) return 0;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

/** Point `meters` away from `[lon, lat]` along `bearingDeg`. */
export function offset(lonLat: [number, number], bearingDeg: number, meters: number): [number, number] {
  const rad = (bearingDeg * Math.PI) / 180;
  const dLat = (meters * Math.cos(rad)) / M_PER_DEG_LAT;
  const dLon = (meters * Math.sin(rad)) / (M_PER_DEG_LAT * Math.cos((lonLat[1] * Math.PI) / 180));
  return [lonLat[0] + dLon, lonLat[1] + dLat];
}

function ground(map: maplibregl.Map, lonLat: [number, number]): number {
  return map.queryTerrainElevation(lonLat) ?? 0;
}

/** Moves the camera behind the walker at `distanceM` along the route. */
export function applyChaseCamera(map: maplibregl.Map, profile: RouteProfile[], distanceM: number): void {
  if (profile.length === 0) return;
  const here = sampleProfile(profile, distanceM).position;
  const heading = bearingAt(profile, distanceM);
  const from = offset(here, heading + 180, CHASE.backM);
  const to = sampleProfile(profile, distanceM + CHASE.aheadM).position;
  const fromAlt = Math.max(ground(map, from), ground(map, here)) + CHASE.heightM * MARS_TO_RENDER;
  const opts = map.calculateCameraOptionsFromTo(
    maplibregl.LngLat.convert(from),
    fromAlt,
    maplibregl.LngLat.convert(to),
    ground(map, to),
  );
  map.jumpTo(opts);
}

export type ViewPreset = "overview" | "top" | "ground";

/** Applies a named view. Ground level keeps the current spot and bearing. */
export function applyPreset(
  map: maplibregl.Map,
  preset: ViewPreset,
  bbox: [number, number, number, number],
): void {
  const [w, s, e, n] = bbox;
  if (preset === "overview") {
    map.fitBounds([w, s, e, n], { pitch: 62, bearing: -24, padding: 40, duration: 1600 });
  } else if (preset === "top") {
    map.fitBounds([w, s, e, n], { pitch: 0, bearing: 0, padding: 40, duration: 1200 });
  } else {
    map.easeTo({ pitch: 80, zoom: Math.max(map.getZoom(), 16.6), duration: 1600 });
  }
}
