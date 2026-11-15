/** Images au sol les plus proches de la cible sélectionnée (fiche de cible, EF-09). */
import { useQuery } from "@tanstack/react-query";
import { nearestImages, thumbSrc, useGroundImages, useViewer } from "./data";
import { api, type LonLat, type Target } from "@/shared/api/client";
import { formatMarsDistance } from "@/shared/geodesy";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { Panel } from "@/shared/ui";

function useTargets(siteId: string) {
  return useQuery({
    queryKey: queryKeys.targets(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/targets", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Targets unavailable");
      return data as Target[];
    },
  });
}

export function NearbyImages() {
  const siteId = useShared((s) => s.siteId);
  const targetId = useShared((s) => s.selectedTargetId);
  const images = useGroundImages();
  const targets = useTargets(siteId);
  const open = useViewer((s) => s.open);
  const target = targets.data?.find((t) => t.id === targetId);
  const count = images.data?.length ?? 0;
  return (
    <Panel title="Ground images">
      {images.isError && <p className="text-sm">Ground images unavailable.</p>}
      {images.data && !target && (
        <p className="text-sm text-[var(--text-muted)]">
          {count} Perseverance images at this site. Click a blue dot on the map, or
          select a target to see nearby images.
        </p>
      )}
      {images.data && target && (
        <>
          <p className="mb-2 text-sm">Nearest to {target.name}:</p>
          <ul className="grid grid-cols-2 gap-2" aria-label={`Nearest to ${target.name}`}>
            {nearestImages(images.data, target.position as LonLat).map(({ image, distance }) => {
              const src = thumbSrc(image.props);
              return (
                <li key={image.id}>
                  <button
                    type="button"
                    onClick={() => open(image)}
                    className="flex w-full flex-col gap-1 text-left text-xs"
                    aria-label={`Open ${image.props.image_id}`}
                  >
                    {src ? (
                      <img src={src} alt="" className="h-20 w-full rounded object-cover" loading="lazy" />
                    ) : (
                      <span className="flex h-20 items-center justify-center rounded bg-[var(--surface-2)]">—</span>
                    )}
                    <span>
                      Sol {image.props.sol} · {image.props.camera ?? image.props.instrument}
                    </span>
                    <span className="text-[var(--text-muted)]">{formatMarsDistance(Math.round(distance))}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Panel>
  );
}
