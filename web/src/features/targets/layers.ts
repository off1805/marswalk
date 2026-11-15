/**
 * Couches deck.gl pour F2 : cibles (ScatterplotLayer pickable + drag),
 * zones interdites/pénalisées (GeoJsonLayer), itinéraires (PathLayer),
 * point de non-retour (TextLayer).
 *
 * Règle R3 : toute distance passe par shared/geodesy.ts.
 * Règle ENF-06 : la couleur n'est jamais le seul indice pour les zones.
 */
import {
  ScatterplotLayer,
  GeoJsonLayer,
  PathLayer,
  TextLayer,
} from "@deck.gl/layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from "geojson";
import type { MapContext } from "@/app/feature";
import type { Target, Route, FeatureCollection as ApiFC } from "@/shared/api/client";
import { colors, hexToRgb } from "@/shared/theme";

/** Couleurs RGBA en tableau pour deck.gl */
function rgba(hex: string, a = 255): [number, number, number, number] {
  const [r, g, b] = hexToRgb(hex);
  return [r, g, b, a];
}

const FORBIDDEN_COLOR = rgba("#d55e00", 160); // orange-rouge, danger
const PENALIZED_COLOR = rgba("#e69f00", 100); // jaune, caution
const FORBIDDEN_LINE = rgba("#d55e00", 220);
const PENALIZED_LINE = rgba("#e69f00", 180);

const VARIANT_COLOR: Record<string, [number, number, number, number]> = {
  safest: rgba(colors.route.safest, 230),
  fastest: rgba(colors.route.fastest, 230),
  science: rgba(colors.route.science, 230),
};

export interface LayerCallbacks {
  onTargetClick: (targetId: string) => void;
  onTargetDragStart: (targetId: string) => void;
  onTargetDrag: (targetId: string, lon: number, lat: number) => void;
  onTargetDragEnd: (targetId: string, lon: number, lat: number) => void;
  onMapClick: (lon: number, lat: number) => void;
  onHazardHover: (cause: string | null) => void;
}

export function buildLayers(
  ctx: MapContext,
  targets: Target[],
  hazards: ApiFC | undefined,
  routes: Route[],
  activeRouteId: string | null,
  selectedTargetId: string | null,
  pickMode: string,
  draggingTargetId: string | null,
  callbacks: LayerCallbacks,
): Layer[] {
  const layers: Layer[] = [];

  // ── 1. Zone de capture de clics carte (workaround pickMode=addTarget) ────
  if (pickMode === "addTarget" && ctx.manifest.bbox) {
    const [w, s, e, n] = ctx.manifest.bbox;
    const pickData: FeatureCollection<Geometry, GeoJsonProperties> = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
          },
          properties: {},
        },
      ],
    };
    layers.push(
      new GeoJsonLayer({
        id: "f2-pick-area",
        data: pickData,
        pickable: true,
        filled: true,
        getFillColor: [0, 0, 0, 0],
        onClick: (info: PickingInfo) => {
          if (info.coordinate && info.coordinate.length >= 2) {
            callbacks.onMapClick(info.coordinate[0]!, info.coordinate[1]!);
          }
          return true;
        },
      }),
    );
  }

  // ── 2. Zones interdites et pénalisées ────────────────────────────────────
  if (hazards?.features?.length) {
    const forbiddenFeatures = hazards.features.filter(
      (f) => f.properties?.["kind"] === "forbidden",
    );
    const penalizedFeatures = hazards.features.filter(
      (f) => f.properties?.["kind"] === "penalized",
    );

    if (forbiddenFeatures.length > 0) {
      const forbiddenData: FeatureCollection<Geometry, GeoJsonProperties> = {
        type: "FeatureCollection",
        features: forbiddenFeatures as Feature<Geometry, GeoJsonProperties>[],
      };
      layers.push(
        new GeoJsonLayer({
          id: "f2-hazard-forbidden",
          data: forbiddenData,
          pickable: true,
          filled: true,
          stroked: true,
          getFillColor: FORBIDDEN_COLOR,
          getLineColor: FORBIDDEN_LINE,
          lineWidthMinPixels: 1,
          onHover: (info: PickingInfo) => {
            if (info.object) {
              const props = (info.object as Feature<Geometry, GeoJsonProperties>).properties;
              const cause = (props as Record<string, unknown> | null)?.["cause"] as string | undefined;
              callbacks.onHazardHover(cause ?? "Zone interdite");
            } else {
              callbacks.onHazardHover(null);
            }
          },
        }),
      );
    }

    if (penalizedFeatures.length > 0) {
      const penalizedData: FeatureCollection<Geometry, GeoJsonProperties> = {
        type: "FeatureCollection",
        features: penalizedFeatures as Feature<Geometry, GeoJsonProperties>[],
      };
      layers.push(
        new GeoJsonLayer({
          id: "f2-hazard-penalized",
          data: penalizedData,
          pickable: true,
          filled: true,
          stroked: true,
          getFillColor: PENALIZED_COLOR,
          getLineColor: PENALIZED_LINE,
          lineWidthMinPixels: 1,
          onHover: (info: PickingInfo) => {
            if (info.object) {
              const props = (info.object as Feature<Geometry, GeoJsonProperties>).properties;
              const cause = (props as Record<string, unknown> | null)?.["cause"] as string | undefined;
              callbacks.onHazardHover(cause ?? "Penalized zone");
            } else {
              callbacks.onHazardHover(null);
            }
          },
        }),
      );
    }
  }

  // ── 3. Itinéraires ─────────────────────────────────────────────────────────
  for (const route of routes) {
    const isActive = route.id === activeRouteId;
    const color = VARIANT_COLOR[route.variant] ?? rgba(colors.info, 200);
    const coords = route.geometry.coordinates as [number, number][];

    layers.push(
      new PathLayer({
        id: `f2-route-${route.id}`,
        data: [{ path: coords, variant: route.variant }],
        pickable: false,
        getPath: (d: { path: [number, number][] }) => d.path,
        getColor: color,
        getWidth: isActive ? 5 : 2,
        widthUnits: "pixels",
        widthMinPixels: isActive ? 4 : 2,
        opacity: isActive ? 1 : 0.5,
      }),
    );
  }

  // ── 4. Point de non-retour ─────────────────────────────────────────────────
  const activeRoute = routes.find((r) => r.id === activeRouteId);
  if (activeRoute?.return_check.point_of_no_return) {
    const pnr = activeRoute.return_check.point_of_no_return as [number, number];
    layers.push(
      new TextLayer({
        id: "f2-pnr",
        data: [{ position: pnr, text: "⏱ PNR" }],
        getPosition: (d: { position: [number, number] }) => [d.position[0], d.position[1], 0],
        getText: (d: { text: string }) => d.text,
        getSize: 14,
        getColor: rgba(colors.caution, 255),
        getTextAnchor: "start",
        getAlignmentBaseline: "center",
        fontWeight: "bold",
        billboard: true,
        // Atlas construit depuis les textes affichés : le jeu ASCII par défaut de deck.gl
        // n'a ni les accents (« Unité à olivine ») ni ⏱ (observation O1).
        characterSet: "auto",
      }),
    );
  }

  // ── 5. Cibles ──────────────────────────────────────────────────────────────
  if (targets.length > 0) {
    layers.push(
      new ScatterplotLayer({
        id: "f2-targets",
        data: targets,
        pickable: true,
        getPosition: (t: Target) => [t.position[0], t.position[1], 0],
        getRadius: (t: Target) => (t.id === selectedTargetId ? 18 : 12),
        radiusUnits: "pixels",
        radiusMinPixels: 8,
        getFillColor: (t: Target): [number, number, number, number] => {
          if (t.id === selectedTargetId) return rgba(colors.info, 255);
          if (t.id === draggingTargetId) return rgba(colors.accent, 255);
          return rgba(colors.ok, 220);
        },
        getLineColor: rgba("#ffffff", 220),
        lineWidthMinPixels: 2,
        stroked: true,
        onClick: (info: PickingInfo) => {
          if (info.object) {
            const t = info.object as Target;
            callbacks.onTargetClick(t.id);
          }
          return true;
        },
      }),
    );

    // Étiquettes des cibles
    layers.push(
      new TextLayer({
        id: "f2-target-labels",
        data: targets,
        pickable: false,
        getPosition: (t: Target) => [t.position[0], t.position[1], 0],
        getText: (t: Target) => t.name,
        getSize: 12,
        getColor: rgba("#ffffff", 230),
        getTextAnchor: "start",
        getAlignmentBaseline: "top",
        getPixelOffset: [16, -4],
        billboard: true,
        fontWeight: "bold",
        // Voir f2-pnr : atlas tiré des noms de cibles, accents compris (O1).
        characterSet: "auto",
      }),
    );

    // Indicateurs de priorité (sans couleur seule — ENF-06)
    layers.push(
      new TextLayer({
        id: "f2-target-priority",
        data: targets.filter((t) => t.priority !== undefined),
        pickable: false,
        getPosition: (t: Target) => [t.position[0], t.position[1], 0],
        getText: (t: Target) =>
          t.priority !== undefined ? `P${t.priority}` : "",
        getSize: 10,
        getColor: rgba(colors.caution, 220),
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
        getPixelOffset: [0, -26],
        billboard: true,
        // Atlas construit depuis les textes affichés : le jeu ASCII par défaut de deck.gl
        // n'a ni les accents (« Unité à olivine ») ni ⏱ (observation O1).
        characterSet: "auto",
      }),
    );
  }

  return layers;
}
