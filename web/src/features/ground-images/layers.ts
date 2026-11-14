/** Couches deck.gl des images au sol : trajet du rover et points de prise de vue. */
import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { Layer } from "@deck.gl/core";
import { toImages, useViewer, type GroundImage } from "./data";
import type { MapContext } from "@/app/feature";
import type { FeatureCollection, LonLat } from "@/shared/api/client";
import { hexToRgb } from "@/shared/theme";

const IMAGE_COLOR = hexToRgb("#56b4e9");
const TRAVERSE_COLOR = hexToRgb("#f0e442");

interface TraversePath {
  path: LonLat[];
}

function isVisible(ctx: MapContext, layerId: string): boolean {
  return ctx.state.layers[layerId]?.visible ?? true;
}

export function groundImageLayers(ctx: MapContext): Layer[] {
  const { manifest, siteId } = ctx;
  const has = (id: string) => manifest.layers.some((l) => l.id === id && l.vector && l.status !== "missing");
  const layers: Layer[] = [];
  if (has("rover_traverse") && isVisible(ctx, "rover_traverse")) {
    layers.push(
      new PathLayer<TraversePath>({
        id: "g1-rover-traverse",
        data: `/api/sites/${siteId}/vector/rover_traverse`,
        dataTransform: ((fc: FeatureCollection) =>
          (fc.features ?? []).flatMap((f) =>
            f.geometry?.type === "LineString" ? [{ path: f.geometry.coordinates as LonLat[] }] : [],
          )) as never,
        getPath: (d) => d.path,
        getColor: [...TRAVERSE_COLOR, 220],
        getWidth: 3,
        widthUnits: "pixels",
        opacity: ctx.state.layers.rover_traverse?.opacity ?? 1,
      }),
    );
  }
  if (isVisible(ctx, "ground_images")) {
    layers.push(
      new ScatterplotLayer<GroundImage>({
        id: "g1-ground-images",
        data: `/api/sites/${siteId}/ground-images`,
        dataTransform: ((fc: FeatureCollection) => toImages(fc)) as never,
        getPosition: (d) => d.position,
        getRadius: 7,
        radiusUnits: "pixels",
        getFillColor: [...IMAGE_COLOR, 230],
        getLineColor: [20, 20, 20, 255],
        lineWidthMinPixels: 1.5,
        stroked: true,
        pickable: true,
        opacity: ctx.state.layers.ground_images?.opacity ?? 1,
        onClick: (info) => {
          if (info.object) useViewer.getState().open(info.object as GroundImage);
          return true;
        },
      }),
    );
  }
  return layers;
}
