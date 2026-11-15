import { tileUrl } from "@/shared/api/client";
import type { MapContext, MapSourceSpec } from "@/app/feature";

/**
 * Génère dynamiquement les sources et couches MapLibre selon l'état du magasin Zustand (F1).
 */
export function getMapSources(ctx: MapContext): MapSourceSpec[] {
  const specs: MapSourceSpec[] = [];
  const { manifest, state, siteId } = ctx;

  for (const layer of manifest.layers) {
    const view = state.layers[layer.id];
    // On n'ajoute que les couches raster disposant de tuiles et rendues visibles
    if (!layer.tiles || !view?.visible) {
      continue;
    }

    const sourceId = `raster-${layer.id}`;
    const layerSpecId = `layer-${layer.id}`;

    specs.push({
      id: sourceId,
      source: {
        type: "raster",
        tiles: [tileUrl(siteId, layer.id, layer.tiles.format)],
        tileSize: layer.tiles.tile_size ?? 256,
        minzoom: layer.tiles.minzoom,
        maxzoom: layer.tiles.maxzoom,
        bounds: manifest.bbox as [number, number, number, number],
        attribution: `${layer.title} · ${layer.source.instrument}`,
      },
      layers: [
        {
          id: layerSpecId,
          type: "raster",
          source: sourceId,
          paint: {
            "raster-opacity": view.opacity ?? 1.0,
          },
        },
      ],
    });
  }

  return specs;
}
