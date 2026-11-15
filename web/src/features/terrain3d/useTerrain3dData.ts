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
import { measureReferenceElevation } from "./demProtocol";
import type { RouteProfile } from "./flyover";
import type { Route, Target } from "@/shared/api/client";
import type { TerrainTarget, TerrainPhoto } from "./TerrainCanvas";

/** Images au sol de l'API, réduites à ce que la 3D affiche. */
function toPhotos(data: unknown): TerrainPhoto[] {
  if (!data) return [];
  const items = Array.isArray(data)
    ? (data as { id: string; position: [number, number]; props: Record<string, unknown> }[])
    : ((data as GeoJSON.FeatureCollection).features ?? []).flatMap((f) =>
        f.geometry?.type === "Point"
          ? [{ id: String(f.id ?? f.properties?.image_id), position: f.geometry.coordinates as [number, number], props: f.properties ?? {} }]
          : [],
      );
  return items.map(({ id, position, props }) => {
    const thumb = (props.thumb as string | null | undefined) ?? null;
    const local = thumb && (/^(https?:)?\/\//.test(thumb) || thumb.startsWith("/")) ? thumb : null;
    return {
      id,
      position,
      sol: Number(props.sol ?? 0),
      camera: String(props.camera ?? props.instrument ?? "Rover camera"),
      thumb: local ?? ((props.thumb_url as string | null | undefined) ?? null),
      url: (props.url as string | null | undefined) ?? null,
      credit: (props.credit as string | null | undefined) ?? null,
    };
  });
}

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
  /** Altitude de référence du site (m) : le maillage 3D est exprimé par rapport à elle. */
  referenceM: number;
  /** Zooms servis par les tuiles du site. */
  zoomRange: [number, number];
  /** Cibles du site, posées sur le terrain. */
  targets: TerrainTarget[];
  /** Trajet du rover (lignes), vide si le site n'en a pas. */
  traverse: [number, number][][];
  /** Images prises au sol par le rover, à sa position du moment. */
  photos: TerrainPhoto[];
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
  const siteId = useShared((s) => s.siteId);
  const activePlanId = useShared((s) => s.activePlanId);
  const activeRouteId = useShared((s) => s.activeRouteId);

  const { data: plan, isLoading: planLoading } = useQuery({
    queryKey: queryKeys.plan(activePlanId ?? ""),
    queryFn: async () => {
      if (!activePlanId) return null;
      const { data, error } = await api.GET("/api/plans/{plan_id}", {
        params: { path: { plan_id: activePlanId } },
      });
      if (error || !data) throw new Error("Plan unavailable");
      return data;
    },
    enabled: Boolean(activePlanId),
    staleTime: 10_000,
  });

  // Cibles du site : même clé de cache que la carte, donc partagées avec elle.
  const { data: targetList } = useQuery({
    queryKey: queryKeys.targets(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/targets", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Targets unavailable");
      return data as Target[];
    },
    staleTime: 30_000,
  });
  const targets: TerrainTarget[] = useMemo(
    () => (targetList ?? []).map((t) => ({ id: t.id, name: t.name, position: t.position as [number, number] })),
    [targetList],
  );

  // Trajet et images du rover, si le paquet du site les contient.
  const hasLayer = (id: string) =>
    Boolean(manifest?.layers.some((l) => l.id === id && l.vector && l.status !== "missing"));
  const hasTraverse = hasLayer("rover_traverse");
  const hasPhotos = hasLayer("ground_images");
  const { data: traverseFc } = useQuery({
    queryKey: ["terrain3d", "traverse", siteId],
    queryFn: async () => {
      const res = await fetch(`/api/sites/${siteId}/vector/rover_traverse`);
      if (!res.ok) throw new Error("Rover traverse unavailable");
      return (await res.json()) as GeoJSON.FeatureCollection;
    },
    enabled: hasTraverse,
    staleTime: Infinity,
  });
  const { data: photoFc } = useQuery({
    // Clé propre à la 3D : la carte met dans queryKeys.groundImages une liste transformée.
    queryKey: ["terrain3d", "photos", siteId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/ground-images", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Ground images unavailable");
      return data as unknown as GeoJSON.FeatureCollection;
    },
    enabled: hasPhotos,
    staleTime: Infinity,
  });
  const traverse = useMemo(
    () =>
      (traverseFc?.features ?? []).flatMap((f) =>
        f.geometry?.type === "LineString" ? [f.geometry.coordinates as [number, number][]] : [],
      ),
    [traverseFc],
  );
  const photos: TerrainPhoto[] = useMemo(() => toPhotos(photoFc), [photoFc]);

  // Altitude de référence : milieu de la plage du MNT. Les zooms : ceux de l'imagerie.
  const { fallbackRefM, zoomRange } = useMemo(() => {
    const dem = manifest?.layers.find((l) => l.id === "dem");
    const range = dem?.value_range as [number, number] | null | undefined;
    const ref = range ? (range[0] + range[1]) / 2 : 0;
    const tex = manifest?.layers.find((l) => l.tiles && l.status !== "missing" && (l.id === "hirise_vis" || l.id === "ctx_vis"));
    const zr: [number, number] = [tex?.tiles?.minzoom ?? 12, Math.min(tex?.tiles?.maxzoom ?? 16, dem?.tiles?.maxzoom ?? 16)];
    return { fallbackRefM: ref, zoomRange: zr };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest?.site_id]);

  // Altitude médiane réelle du site, mesurée sur ses tuiles d'altitude les plus grossières.
  const reference = useQuery({
    queryKey: ["terrain3d", "reference", manifest?.site_id],
    queryFn: async () => {
      const m = manifest!;
      return measureReferenceElevation(
        `/tiles/${m.site_id}/terrain_rgb/{z}/{x}/{y}.png`,
        m.bbox as [number, number, number, number],
        zoomRange[0] + 1,
      );
    },
    enabled: Boolean(manifest),
    staleTime: Infinity,
    retry: false,
  });
  const referenceM = reference.data ?? fallbackRefM;

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
    referenceM,
    zoomRange,
    targets,
    traverse,
    photos,
    isLoading: manifestLoading || planLoading || reference.isLoading,
  };
}
