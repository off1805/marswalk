/** Données des images au sol (G1) : requête, sélection, images les plus proches. */
import { useQuery } from "@tanstack/react-query";
import { create } from "zustand";
import { api, type FeatureCollection, type LonLat } from "@/shared/api/client";
import { distanceM } from "@/shared/geodesy";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";

/** Propriétés d'une image de l'index (pipeline G1). */
export interface GroundImageProps {
  image_id: string;
  sol: number;
  instrument: string;
  camera?: string | null;
  thumb?: string | null;
  thumb_url?: string | null;
  url?: string | null;
  utc?: string | null;
  azimuth_deg?: number | null;
  credit?: string | null;
  position_source?: string | null;
}

export interface GroundImage {
  id: string;
  position: LonLat;
  props: GroundImageProps;
}

/** Images de l'index, avec leur position (les entités sans point sont ignorées). */
export function toImages(fc: FeatureCollection | undefined | null): GroundImage[] {
  return (fc?.features ?? []).flatMap((f) => {
    const g = f.geometry;
    if (!g || g.type !== "Point") return [];
    const props = (f.properties ?? {}) as unknown as GroundImageProps;
    if (!props.image_id) return [];
    return [{ id: String(f.id ?? props.image_id), position: g.coordinates as LonLat, props }];
  });
}

/** Adresse affichable de la vignette : une URL absolue, sinon le lien distant du JPL. */
export function thumbSrc(p: GroundImageProps): string | null {
  const local = p.thumb ?? null;
  if (local && /^(https?:)?\/\//.test(local)) return local;
  if (local && local.startsWith("/")) return local;
  return p.thumb_url ?? null;
}

/** Les ``n`` images les plus proches d'un point, avec leur distance en mètres. */
export function nearestImages(images: GroundImage[], point: LonLat, n = 4) {
  return images
    .map((image) => ({ image, distance: distanceM(point, image.position) }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, n);
}

export function useGroundImages() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.groundImages(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/ground-images", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Ground images unavailable");
      return toImages(data as FeatureCollection);
    },
    staleTime: Infinity,
  });
}

/** Image ouverte dans la visionneuse (état propre à la fonctionnalité). */
interface ViewerState {
  selected: GroundImage | null;
  open: (image: GroundImage | null) => void;
}

export const useViewer = create<ViewerState>()((set) => ({
  selected: null,
  open: (selected) => set({ selected }),
}));
