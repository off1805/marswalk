/**
 * Couches deck.gl de F3 : un repère à la distance survolée (`hoverDistanceM`) et une bande
 * de capture invisible le long de l'itinéraire affiché, dont le survol écrit
 * `hoverDistanceM`. Le tracé visible des variantes reste celui de F2.
 *
 * `mapLayers` est appelée par la coquille comme une fonction pure : elle lit le plan dans
 * le cache TanStack Query, dont le client est injecté par ProfilePanel (même principe que F2).
 */
import type { Layer, PickingInfo } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { QueryClient } from "@tanstack/react-query";
import type { MapContext } from "@/app/feature";
import type { Plan } from "@/shared/api/client";
import type { LonLat } from "@/shared/geodesy";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { hexToRgb, colors } from "@/shared/theme";
import { nearestDistance, positionAtDistance, selectProfileRoute } from "./profileData";

let qcRef: QueryClient | null = null;
export function injectQueryClient(qc: QueryClient): void {
  qcRef = qc;
}

/** Au-delà de cet écart, un survol de carte n'est pas rattaché à l'itinéraire. */
const MAX_HOVER_OFFSET_M = 40;

/** Vrai quand c'est la carte qui a posé le repère courant (pour l'effacer en sortant). */
let hoverFromMap = false;

export function onRouteHover(plan: Plan, info: Pick<PickingInfo, "coordinate" | "object">): void {
  const { activeRouteId, hoverDistanceM, setHoverDistance } = useShared.getState();
  const choice = selectProfileRoute(plan, activeRouteId);
  const coord = info.coordinate;
  if (!choice || !info.object || !coord || coord.length < 2) {
    if (hoverFromMap && hoverDistanceM !== null) setHoverDistance(null);
    hoverFromMap = false;
    return;
  }
  const hit = nearestDistance(choice.route.profile, [coord[0]!, coord[1]!]);
  if (!hit || hit.offsetM > MAX_HOVER_OFFSET_M) return;
  hoverFromMap = true;
  if (hit.distanceM !== hoverDistanceM) setHoverDistance(hit.distanceM);
}

export function buildProfileLayers(
  plan: Plan | undefined,
  activeRouteId: string | null,
  hoverDistanceM: number | null,
): Layer[] {
  const choice = selectProfileRoute(plan, activeRouteId);
  if (!plan || !choice) return [];
  const path: LonLat[] = choice.route.profile.map((p) => p.position);
  const layers: Layer[] = [
    new PathLayer<{ path: LonLat[] }>({
      id: "f3-route-hover",
      data: [{ path }],
      getPath: (d) => d.path,
      getColor: [0, 0, 0, 0],
      widthUnits: "pixels",
      getWidth: 16,
      pickable: true,
      onHover: (info) => onRouteHover(plan, info),
    }),
  ];
  const pos = hoverDistanceM == null ? null : positionAtDistance(choice.route.profile, hoverDistanceM);
  if (pos) {
    layers.push(
      new ScatterplotLayer<{ position: LonLat }>({
        id: "f3-hover-marker",
        data: [{ position: pos }],
        getPosition: (d) => d.position,
        radiusUnits: "pixels",
        getRadius: 7,
        getFillColor: [...hexToRgb(colors.route[choice.route.variant] ?? colors.accent), 255],
        stroked: true,
        getLineColor: [255, 255, 255, 255],
        lineWidthUnits: "pixels",
        getLineWidth: 2,
        pickable: false,
      }),
    );
  }
  return layers;
}

export function mapLayers(ctx: MapContext): Layer[] {
  const { activePlanId, activeRouteId, hoverDistanceM } = ctx.state;
  const plan = activePlanId && qcRef ? qcRef.getQueryData<Plan>(queryKeys.plan(activePlanId)) : undefined;
  return buildProfileLayers(plan, activeRouteId, hoverDistanceM);
}
