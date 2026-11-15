/**
 * Calculs purs du profil d'itinéraire (F3), sans React ni ECharts.
 *
 * Tout part de l'objet `Route` du plan (contrat §6) : `profile` (échantillons tous les 5 m),
 * `segments` (tronçons) et `totals`. Les distances le long de l'itinéraire sont celles du
 * planificateur (P3) ; seule la recherche du point le plus proche d'un survol de carte
 * mesure une distance, et elle passe par la géodésie martienne (règle R3).
 */
import type { Plan, Route } from "@/shared/api/client";
import { distanceM, type LonLat } from "@/shared/geodesy";

export type ProfileSample = Route["profile"][number];
export type RouteSegment = Route["segments"][number];

// ---------------------------------------------------------------------------
// Choix de l'itinéraire affiché
// ---------------------------------------------------------------------------

export interface ProfileRouteChoice {
  route: Route;
  /** Vrai quand aucune variante n'est choisie : le profil montre un aperçu. */
  preview: boolean;
}

/**
 * Itinéraire à afficher : la variante active du magasin partagé, sinon celle retenue dans le
 * plan (état « selected »), sinon la plus sûre en aperçu. F3 ne choisit jamais de variante à la place de
 * l'astronaute : l'aperçu ne touche pas à `activeRouteId`.
 */
export function selectProfileRoute(
  plan: Plan | null | undefined,
  activeRouteId: string | null,
): ProfileRouteChoice | null {
  if (!plan || plan.routes.length === 0) return null;
  const byId = (id: string | null | undefined) =>
    id ? plan.routes.find((r) => r.id === id) : undefined;
  // `selected_route_id` ne compte que si le plan est à l'état « selected » : à l'état
  // « computed », le serveur peut le remplir par défaut sans que l'astronaute ait choisi.
  const retained = plan.status === "selected" ? byId(plan.selected_route_id) : undefined;
  const active = byId(activeRouteId) ?? retained;
  if (active) return { route: active, preview: false };
  const fallback = plan.routes.find((r) => r.variant === "safest") ?? plan.routes[0]!;
  return { route: fallback, preview: true };
}

// ---------------------------------------------------------------------------
// Bandes de pente
// ---------------------------------------------------------------------------

export type SlopeLevel = "caution" | "danger";

export interface SlopeBand {
  level: SlopeLevel;
  fromM: number;
  toM: number;
  maxSlopeDeg: number;
}

export interface SlopeThresholds {
  /** Pente pénalisée (bande orange), `penalty_slope_deg` des réglages. */
  penaltyDeg: number;
  /** Pente interdite (bande rouge), `max_slope_deg` des réglages. */
  maxDeg: number;
}

export function slopeLevel(slopeDeg: number | null | undefined, t: SlopeThresholds): SlopeLevel | null {
  if (slopeDeg == null) return null;
  const s = Math.abs(slopeDeg);
  if (s >= t.maxDeg) return "danger";
  if (s >= t.penaltyDeg) return "caution";
  return null;
}

/**
 * Regroupe les échantillons consécutifs de même niveau en bandes. Un échantillon couvre
 * l'intervalle qui va jusqu'au suivant ; le dernier couvre un pas de 5 m au plus.
 */
export function slopeBands(profile: ProfileSample[], t: SlopeThresholds): SlopeBand[] {
  const bands: SlopeBand[] = [];
  let cur: SlopeBand | null = null;
  for (let i = 0; i < profile.length; i++) {
    const p = profile[i]!;
    const next = profile[i + 1];
    const end = next ? next.distance_m : p.distance_m;
    const level = slopeLevel(p.slope_deg, t);
    const slope = Math.abs(p.slope_deg ?? 0);
    if (level && cur && cur.level === level && cur.toM >= p.distance_m - 1e-6) {
      cur.toM = end;
      cur.maxSlopeDeg = Math.max(cur.maxSlopeDeg, slope);
    } else if (level) {
      cur = { level, fromM: p.distance_m, toM: end, maxSlopeDeg: slope };
      bands.push(cur);
    } else {
      cur = null;
    }
  }
  return bands;
}

// ---------------------------------------------------------------------------
// Tronçons, cibles et point de non-retour
// ---------------------------------------------------------------------------

export interface SegmentSpan {
  index: number;
  fromM: number;
  toM: number;
  fromLabel: string;
  toLabel: string;
  toTargetId: string | null;
  distanceM: number;
  walkS: number;
  workS: number;
  ascentM: number;
  descentM: number;
  maxSlopeDeg: number;
}

/** Bornes cumulées de chaque tronçon et libellés lisibles (« Habitat → Front du delta »). */
export function segmentSpans(
  route: Route,
  targetNames: Record<string, string> = {},
): SegmentSpan[] {
  const label = (id: string | null) => (id ? (targetNames[id] ?? id) : "Habitat");
  let acc = 0;
  return route.segments.map((s) => {
    const fromM = acc;
    acc += s.distance_m;
    return {
      index: s.index,
      fromM,
      toM: acc,
      fromLabel: label(s.from_target_id),
      toLabel: label(s.to_target_id),
      toTargetId: s.to_target_id,
      distanceM: s.distance_m,
      walkS: s.duration_s,
      workS: s.work_time_s,
      ascentM: s.ascent_m,
      descentM: s.descent_m,
      maxSlopeDeg: s.max_slope_deg,
    };
  });
}

export interface TargetMarker {
  targetId: string;
  label: string;
  distanceM: number;
  workS: number;
}

/** Une cible par fin de tronçon qui arrive sur une cible (l'habitat n'en est pas une). */
export function targetMarkers(spans: SegmentSpan[]): TargetMarker[] {
  return spans
    .filter((s) => s.toTargetId !== null)
    .map((s) => ({ targetId: s.toTargetId!, label: s.toLabel, distanceM: s.toM, workS: s.workS }));
}

/** Distance du premier échantillon atteint à l'instant t (temps cumulé). */
export function distanceAtTime(profile: ProfileSample[], timeS: number): number | null {
  if (profile.length === 0) return null;
  const hit = profile.find((p) => p.time_s >= timeS);
  return (hit ?? profile[profile.length - 1]!).distance_m;
}

/**
 * Position du point de non-retour sur le profil, s'il tombe avant l'arrivée. Quand il
 * coïncide avec la fin, le retour est garanti tout du long et aucun repère n'est utile.
 */
export function pointOfNoReturnM(route: Route): number | null {
  const t = route.return_check.point_of_no_return_time_s;
  if (t == null || route.profile.length === 0) return null;
  const end = route.profile[route.profile.length - 1]!;
  if (t >= end.time_s - 1) return null;
  return distanceAtTime(route.profile, t);
}

// ---------------------------------------------------------------------------
// Totaux et cohérence avec la variante
// ---------------------------------------------------------------------------

export interface ProfileTotals {
  distanceM: number;
  walkS: number;
  workS: number;
  durationS: number;
  ascentM: number;
  descentM: number;
  maxSlopeDeg: number;
}

/** Totaux recalculés depuis le profil et les tronçons, indépendamment de `route.totals`. */
export function profileTotals(route: Route): ProfileTotals {
  const last = route.profile[route.profile.length - 1];
  const sum = (f: (s: RouteSegment) => number) => route.segments.reduce((a, s) => a + f(s), 0);
  return {
    distanceM: last?.distance_m ?? sum((s) => s.distance_m),
    walkS: sum((s) => s.duration_s),
    workS: sum((s) => s.work_time_s),
    durationS: last?.time_s ?? sum((s) => s.duration_s + s.work_time_s),
    ascentM: sum((s) => s.ascent_m),
    descentM: sum((s) => s.descent_m),
    maxSlopeDeg: route.segments.reduce((a, s) => Math.max(a, s.max_slope_deg), 0),
  };
}

/** Tolérances d'arrondi : un pas d'échantillon ne doit pas créer de faux écart. */
const TOLERANCE = { distanceM: 1, timeS: 1, elevationM: 0.5, slopeDeg: 0.1 } as const;

export interface TotalsMismatch {
  field: keyof ProfileTotals;
  profile: number;
  variant: number;
}

/** Écarts entre les totaux recalculés et ceux de la variante ; vide si tout concorde. */
export function compareTotals(route: Route): TotalsMismatch[] {
  const p = profileTotals(route);
  const v = route.totals;
  const checks: [keyof ProfileTotals, number, number, number][] = [
    ["distanceM", p.distanceM, v.distance_m, TOLERANCE.distanceM],
    ["walkS", p.walkS, v.walk_time_s, TOLERANCE.timeS],
    ["workS", p.workS, v.work_time_s, TOLERANCE.timeS],
    ["durationS", p.durationS, v.duration_s, TOLERANCE.timeS],
    ["ascentM", p.ascentM, v.ascent_m, TOLERANCE.elevationM],
    ["descentM", p.descentM, v.descent_m, TOLERANCE.elevationM],
    ["maxSlopeDeg", p.maxSlopeDeg, v.max_slope_deg, TOLERANCE.slopeDeg],
  ];
  return checks
    .filter(([, a, b, tol]) => Math.abs(a - b) > tol)
    .map(([field, profile, variant]) => ({ field, profile, variant }));
}

// ---------------------------------------------------------------------------
// Synchronisation du survol (hoverDistanceM)
// ---------------------------------------------------------------------------

/** Indice de l'échantillon le plus proche d'une distance cumulée (recherche dichotomique). */
export function sampleIndexAt(profile: ProfileSample[], d: number): number {
  if (profile.length === 0) return -1;
  let lo = 0;
  let hi = profile.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (profile[mid]!.distance_m < d) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(profile[lo - 1]!.distance_m - d) <= Math.abs(profile[lo]!.distance_m - d)) {
    return lo - 1;
  }
  return lo;
}

/** Position interpolée le long du profil à une distance cumulée (pour le repère de carte). */
export function positionAtDistance(profile: ProfileSample[], d: number): LonLat | null {
  if (profile.length === 0) return null;
  const first = profile[0]!;
  const last = profile[profile.length - 1]!;
  if (d <= first.distance_m) return first.position;
  if (d >= last.distance_m) return last.position;
  let i = sampleIndexAt(profile, d);
  if (profile[i]!.distance_m > d) i -= 1;
  const a = profile[i]!;
  const b = profile[i + 1]!;
  const span = b.distance_m - a.distance_m;
  const f = span > 0 ? (d - a.distance_m) / span : 0;
  return [
    a.position[0] + (b.position[0] - a.position[0]) * f,
    a.position[1] + (b.position[1] - a.position[1]) * f,
  ];
}

/**
 * Distance cumulée de l'échantillon le plus proche d'un point de la carte, avec l'écart en
 * mètres. Sur un aller-retour qui repasse au même endroit, le premier passage l'emporte.
 */
export function nearestDistance(
  profile: ProfileSample[],
  point: LonLat,
): { distanceM: number; offsetM: number } | null {
  let best: { distanceM: number; offsetM: number } | null = null;
  for (const p of profile) {
    const off = distanceM(p.position, point);
    if (!best || off < best.offsetM - 1e-9) best = { distanceM: p.distance_m, offsetM: off };
  }
  return best;
}

// ---------------------------------------------------------------------------
// Formats
// ---------------------------------------------------------------------------

export function formatDuration(s: number): string {
  const total = Math.round(s);
  if (total < 60) return `${total} s`;
  const minutes = Math.round(total / 60);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")}`;
}

export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}
