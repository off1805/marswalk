/** Mise en forme et conversions de l'export (X1), sans dépendance au rendu. */
import type { FeatureCollection, LonLat, Schemas } from "@/shared/api/client";
import { MARS_2000_RADIUS_M } from "@/shared/geodesy";

export type Logbook = Schemas["Logbook"];
export type LogbookEntry = Schemas["LogbookEntry"];
export type ProfileSample = Schemas["ProfileSample"];

export const CRS_NOTE = "IAU_2015:49900 (Mars 2000, planetocentric, east longitudes)";

export const KIND_LABELS: Record<LogbookEntry["kind"], string> = {
  start: "Departure",
  target: "Target",
  observation: "Observation",
  alert: "Alert",
  obstacle: "Obstacle",
  reroute: "Reroute",
  end: "End",
};

/** Durée lisible : « 1 h 36 min », « 12 min », « 45 s ». */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const h = Math.floor(s / 3600);
  const min = Math.round((s % 3600) / 60);
  if (h === 0) return `${min} min`;
  return min === 0 ? `${h} h` : `${h} h ${String(min).padStart(2, "0")} min`;
}

/** Distance formatted in metres or kilometres. */
export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}

/** Position lisible, en degrés est et nord (Mars 2000). */
export function formatLonLat(p: LonLat | null | undefined): string {
  if (!p) return "—";
  const [lon, lat] = p;
  return `${lon.toFixed(5)}° E, ${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? "N" : "S"}`;
}

/** Carnet en GeoJSON : un point par entrée positionnée, propriétés plates pour QGIS. */
export function logbookToGeojson(book: Logbook): FeatureCollection {
  return {
    type: "FeatureCollection",
    crs_note: CRS_NOTE,
    features: book.entries.flatMap((e, i) =>
      e.position
        ? [
            {
              type: "Feature" as const,
              id: `${book.eva_id}-${i + 1}`,
              geometry: { type: "Point" as const, coordinates: e.position },
              properties: {
                eva_id: book.eva_id,
                site_id: book.site_id,
                utc: e.utc,
                sol: e.sol,
                lmst: e.lmst,
                kind: e.kind,
                text: e.text,
                ref_id: e.ref_id ?? null,
              },
            },
          ]
        : [],
    ),
  };
}

/** Télécharge un objet JSON sous le nom donné. */
export function downloadJson(name: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 1)], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export interface PlanView {
  /** Coordonnées d'écran d'un point. */
  project: (p: LonLat) => [number, number];
  /** Pixels par mètre. */
  scale: number;
}

/**
 * Vue en plan à l'échelle : projection équirectangulaire locale (règle R1), cadrée sur
 * l'emprise des points avec une marge, sans déformer les distances.
 */
export function planView(points: LonLat[], width: number, height: number, pad = 24): PlanView {
  const lat0 = points.reduce((s, p) => s + p[1], 0) / Math.max(points.length, 1);
  const k = Math.cos((lat0 * Math.PI) / 180);
  const toM = ([lon, lat]: LonLat): [number, number] => [
    MARS_2000_RADIUS_M * ((lon * Math.PI) / 180) * k,
    MARS_2000_RADIUS_M * ((lat * Math.PI) / 180),
  ];
  const xy = points.map(toM);
  const xs = xy.map((p) => p[0]);
  const ys = xy.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const scale = Math.min((width - 2 * pad) / Math.max(x1 - x0, 1), (height - 2 * pad) / Math.max(y1 - y0, 1));
  const ox = (width - (x1 - x0) * scale) / 2;
  const oy = (height - (y1 - y0) * scale) / 2;
  return {
    scale,
    project: (p) => {
      const [x, y] = toM(p);
      return [ox + (x - x0) * scale, height - oy - (y - y0) * scale];
    },
  };
}

/** Longueur ronde (1, 2 ou 5 × 10ⁿ m) d'une barre d'échelle d'au plus ``maxPx`` pixels. */
export function scaleBarMeters(scale: number, maxPx = 120): number {
  const max = maxPx / scale;
  const p = 10 ** Math.floor(Math.log10(max));
  return [5, 2, 1].map((f) => f * p).find((m) => m <= max) ?? p;
}

/** Tracé SVG du profil d'altitude (distance en abscisse), et bornes des axes. */
export function profilePath(samples: ProfileSample[], width: number, height: number, pad = 28) {
  const pts = samples.filter((s) => s.elevation_m !== null && s.elevation_m !== undefined);
  if (pts.length < 2) return null;
  const d1 = pts[pts.length - 1]!.distance_m || 1;
  const els = pts.map((s) => s.elevation_m as number);
  const [e0, e1] = [Math.min(...els), Math.max(...els)];
  const span = Math.max(e1 - e0, 1);
  const x = (d: number) => pad + (d / d1) * (width - 2 * pad);
  const y = (e: number) => height - pad - ((e - e0) / span) * (height - 2 * pad);
  const d = pts
    .map((s, i) => `${i ? "L" : "M"}${x(s.distance_m).toFixed(1)},${y(s.elevation_m as number).toFixed(1)}`)
    .join(" ");
  return { d, minElevation: e0, maxElevation: e1, distance: d1 };
}
