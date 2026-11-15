/**
 * Hook de données pour la vue 3D.
 *
 * Principe S (Single Responsibility) : ce hook ne fait que sélectionner
 * et transformer les données du cache TanStack Query. Il ne sait rien
 * du rendu ni de l'animation.
 *
 * Principe I (Interface Segregation) : il expose exactement ce dont la vue
 * 3D a besoin, pas toute la structure `Plan` ou `SiteManifest`.
 */
import { useMemo } from "react";
import { useSiteManifest } from "@/shared/hooks";
import { useShared } from "@/shared/store";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { buildTerrainConfig, type TerrainConfig } from "./terrain.config";
import type { RouteProfile } from "./flyover";
import type { Route } from "@/shared/api/client";

/** Ce que la vue 3D consomme : config terrain + itinéraire actif. */
export interface Terrain3dData {
  /** Configuration du terrain (URLs, décodeur, bbox). Null si le manifeste charge. */
  terrainConfig: TerrainConfig | null;
  /** Profil de l'itinéraire actif, ou tableau vide si aucun. */
  activeProfile: RouteProfile[];
  /** Géométrie complète de l'itinéraire actif, pour le dessin sur le terrain. */
  activeRoute: Route | null;
  /** Longueur totale de l'itinéraire en mètres. */
  totalDistanceM: number;
  /** Vrai pendant le chargement initial. */
  isLoading: boolean;
}

/**
 * Sélectionne le calque de texture de base dans le manifeste.
 * Priorité : hirise_vis > ctx_vis > hillshade.
 */
function pickTextureLayer(
  layers: { id: string; tiles?: { format: "webp" | "png" } | null; status: string }[],
): { id: string; format: "webp" | "png" } {
  const PRIORITY = ["hirise_vis", "ctx_vis", "hillshade"];
  for (const id of PRIORITY) {
    const layer = layers.find(
      (l) => l.id === id && l.tiles && l.status !== "missing",
    );
    if (layer?.tiles) {
      return { id: layer.id, format: layer.tiles.format };
    }
  }
  // Repli : première couche avec des tuiles
  const fallback = layers.find((l) => l.tiles && l.status !== "missing");
  return fallback?.tiles
    ? { id: fallback.id, format: fallback.tiles.format }
    : { id: "hillshade", format: "webp" };
}

export function useTerrain3dData(): Terrain3dData {
  const { data: manifest, isLoading: manifestLoading } = useSiteManifest();
  const activePlanId = useShared((s) => s.activePlanId);
  const activeRouteId = useShared((s) => s.activeRouteId);

  const { data: plan, isLoading: planLoading } = useQuery({
    queryKey: queryKeys.plan(activePlanId ?? ""),
    queryFn: async () => {
      if (!activePlanId) return null;
      const { data, error } = await api.GET("/api/plans/{plan_id}", {
        params: { path: { plan_id: activePlanId } },
      });
      if (error || !data) throw new Error("Plan indisponible");
      return data;
    },
    enabled: Boolean(activePlanId),
    staleTime: 10_000,
  });

  // Construire la TerrainConfig depuis le manifeste. Mémorisée : une nouvelle référence à
  // chaque rendu relancerait les effets du canevas.
  const terrainConfig: TerrainConfig | null = useMemo(() => {
    if (!manifest) return null;
    const texture = pickTextureLayer(manifest.layers);
    return buildTerrainConfig(
      manifest.site_id,
      manifest.bbox as [number, number, number, number],
      texture.id,
      texture.format,
    );
  }, [manifest]);

  // Itinéraire actif
  const activeRoute: Route | null =
    (plan?.routes.find((r) => r.id === activeRouteId) ??
    plan?.routes[0] ??
    null) as Route | null;

  // Transformer le profil de l'API en RouteProfile plat. Mémorisé (écart E7) : useFlyover
  // remet le survol à zéro quand ce tableau change, il ne doit donc changer qu'avec
  // l'itinéraire.
  const activeProfile: RouteProfile[] = useMemo(
    () =>
      activeRoute
        ? activeRoute.profile.map((s) => ({
            distanceM: s.distance_m,
            position: s.position as [number, number],
            elevationM: s.elevation_m,
          }))
        : [],
    [activeRoute],
  );

  const totalDistanceM = activeRoute?.totals.distance_m ?? 0;

  return {
    terrainConfig,
    activeProfile,
    activeRoute,
    totalDistanceM,
    isLoading: manifestLoading || planLoading,
  };
}
