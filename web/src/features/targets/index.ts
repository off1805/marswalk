/**
 * Cibles et itinéraire (F2).
 *
 * Slots :
 *   - right       : panneau de cibles, fiche et comparateur de variantes.
 *   - left        : panneau « Science du site » (pourquoi Jezero, d'après S1).
 *   - map-overlay : légende des zones et tooltip de survol.
 *
 * Couches deck.gl :
 *   - Zones interdites et pénalisées (GeoJsonLayer)
 *   - Itinéraires par variante (PathLayer)
 *   - Point de non-retour (TextLayer)
 *   - Cibles (ScatterplotLayer pickable, drag & drop)
 *   - Étiquettes et priorités (TextLayer)
 *
 * Ne jamais importer le code d'une autre fonctionnalité (features/<autre>/).
 * Communication via @/shared/store et @/shared/api/client.
 *
 * Architecture des couches :
 * mapLayers() est appelé comme une fonction pure par la coquille (MapView). Elle lit
 * le cache TanStack Query directement via queryClient.getQueryData() en utilisant une
 * référence de QueryClient injectée par le composant TargetsPanel via la fonction
 * setQueryClientRef() ci-dessous.
 */
import type { Feature } from "@/app/feature";
import type { Layer } from "@deck.gl/core";
import type { QueryClient } from "@tanstack/react-query";
import { TargetsPanel } from "./TargetsPanel";
import { TargetsOverlay } from "./TargetsOverlay";
import { SciencePanel } from "./SciencePanel";
import { buildLayers } from "./layers";
import { targetsStore } from "./targetsStore";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { api } from "@/shared/api/client";
import { onMapClick } from "@/shared/mapClick";
import type { Target, FeatureCollection, Plan } from "@/shared/api/client";
import type { MapContext } from "@/app/feature";

// QueryClient injecté par TargetsPanel au premier rendu (dans le contexte React)
let _qc: QueryClient | null = null;
export function injectQueryClient(qc: QueryClient): void {
  _qc = qc;
}

function getMapLayers(ctx: MapContext): Layer[] {
  if (!_qc) return [];

  const { siteId, pickMode, selectedTargetId, activePlanId, activeRouteId, preset } =
    useShared.getState();

  const targets =
    (_qc.getQueryData(queryKeys.targets(siteId)) as Target[] | undefined) ?? [];
  const hazards = _qc.getQueryData(
    queryKeys.hazards(siteId, preset),
  ) as FeatureCollection | undefined;
  const plan = activePlanId
    ? (_qc.getQueryData(queryKeys.plan(activePlanId)) as Plan | undefined)
    : undefined;

  const { draggingTargetId } = targetsStore.getState();

  return buildLayers(
    ctx,
    targets,
    hazards,
    plan?.routes ?? [],
    activeRouteId,
    selectedTargetId,
    pickMode,
    draggingTargetId,
    {
      onTargetClick: (targetId: string) => {
        const { selectTarget, selectedTargetId: cur, pickMode: mode } = useShared.getState();
        // En mode interrogation, le clic interroge le point (F1) au lieu de choisir la cible.
        if (mode === "query") return;
        selectTarget(cur === targetId ? null : targetId);
      },
      onTargetDragStart: (targetId: string) => {
        targetsStore.getState().setDraggingTargetId(targetId);
      },
      onTargetDrag: () => {
        // live position tracked by deck.gl; server update on dragEnd
      },
      onTargetDragEnd: (targetId: string, lon: number, lat: number) => {
        targetsStore.getState().setDraggingTargetId(null);
        void (async () => {
          try {
            await api.PATCH("/api/targets/{target_id}", {
              params: { path: { target_id: targetId } },
              body: { position: [lon, lat] },
            });
            void _qc?.invalidateQueries({ queryKey: queryKeys.targets(siteId) });
          } catch {
            /* silent */
          }
        })();
      },
      onHazardHover: (cause: string | null) => {
        targetsStore.getState().setHazardHoverText(cause);
      },
    },
  );
}

/**
 * Adds a target where the map was clicked, in "addTarget" pick mode. Map clicks come
 * from the shell's click bus (shared/mapClick.ts), read on MapLibre, so they arrive
 * whatever deck.gl layer lies under the pointer.
 */
async function addTargetAt(lon: number, lat: number) {
  const { pickMode: mode, setPickMode, siteId } = useShared.getState();
  if (mode !== "addTarget") return;
  setPickMode("none");
  const { setActionError } = targetsStore.getState();
  setActionError(null);
  const current = (_qc?.getQueryData(queryKeys.targets(siteId)) as Target[] | undefined) ?? [];
  const n = current.length + 1;
  try {
    const { data, error } = await api.POST("/api/sites/{site_id}/targets", {
      params: { path: { site_id: siteId } },
      body: {
        name: `Target ${n}`,
        position: [lon, lat] as [number, number],
        kind: "science" as const,
        priority: 2, // medium; the API accepts 1 (high) to 3 (low)
        work_time_s: 900,
      },
    });
    if (error || !data) {
      const detail = (error as { detail?: unknown } | undefined)?.detail;
      throw new Error(typeof detail === "string" ? detail : "the server refused the target");
    }
    await _qc?.invalidateQueries({ queryKey: queryKeys.targets(siteId) });
  } catch (err) {
    setActionError(`Could not add the target: ${err instanceof Error ? err.message : String(err)}.`);
  }
}

export const feature: Feature = {
  id: "targets",
  panels: [
    { slot: "right", order: 20, component: TargetsPanel },
    { slot: "left", order: 20, component: SciencePanel, modes: ["map"] },
    { slot: "map-overlay", order: 20, component: TargetsOverlay },
  ],
  mapLayers: (ctx: MapContext) => getMapLayers(ctx),
  routes: [],
  setup: () => {
    onMapClick(({ lon, lat }) => void addTargetAt(lon, lat));
  },
};
