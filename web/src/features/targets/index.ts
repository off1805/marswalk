/**
 * Cibles et itinéraire (F2).
 *
 * Slots :
 *   - right       : panneau de cibles, fiche et comparateur de variantes.
 *   - map-overlay : légende des zones et tooltip de survol.
 *
 * Couches deck.gl :
 *   - Zone de capture de clics (mode addTarget)
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
import { buildLayers } from "./layers";
import { targetsStore } from "./targetsStore";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { api } from "@/shared/api/client";
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
      onMapClick: (lon: number, lat: number) => {
        const { pickMode: mode, setPickMode, siteId: sid } = useShared.getState();
        if (mode !== "addTarget") return;
        setPickMode("none");
        const currentTargets =
          (_qc?.getQueryData(queryKeys.targets(sid)) as Target[] | undefined) ?? [];
        void (async () => {
          try {
            const { data } = await api.POST("/api/sites/{site_id}/targets", {
              params: { path: { site_id: sid } },
              body: {
                name: `Cible ${currentTargets.length + 1}`,
                position: [lon, lat] as [number, number],
                kind: "science" as const,
                priority: currentTargets.length + 1,
                work_time_s: 900,
              },
            });
            if (data)
              void _qc?.invalidateQueries({ queryKey: queryKeys.targets(sid) });
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

export const feature: Feature = {
  id: "targets",
  panels: [
    { slot: "right", order: 20, component: TargetsPanel },
    { slot: "map-overlay", order: 20, component: TargetsOverlay },
  ],
  mapLayers: (ctx: MapContext) => getMapLayers(ctx),
  routes: [],
};
