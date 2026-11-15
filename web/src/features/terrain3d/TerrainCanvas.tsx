/**
 * 3D terrain renderer, on MapLibre (the 2D map's engine).
 *
 * - Terrain mesh from the site's terrain-RGB tiles, made relative to the site
 *   (demProtocol.ts), with adjustable vertical exaggeration.
 * - Orbital imagery draped on the mesh, an iron-oxide wash, and hillshading computed
 *   from the same elevation data: slopes facing the light glow, the others fall into
 *   shadow, so dunes, scarps and pits read as relief.
 * - Butterscotch Martian sky with distance fog toward the horizon.
 * - The active route and targets draped on the ground; a marker for the walker.
 * - The rover's traverse, and the spots where it took pictures (click to see one).
 *
 * The camera can tilt to 85°, which brings it down to ground level: drag with the
 * right button (or Ctrl + drag) to tilt, then fly along the ground.
 */
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { Route } from "@/shared/api/client";
import { colors } from "@/shared/theme";
import { applyChaseCamera, applyPreset, MARS_TO_RENDER, type ViewPreset } from "./camera";
import { demTileUrl, registerDemProtocol } from "./demProtocol";
import { sampleProfile, type RouteProfile } from "./flyover";
import type { TerrainConfig } from "./terrain.config";

/** An image taken on the ground by the rover, placed where the rover stood. */
export interface TerrainPhoto {
  id: string;
  position: [number, number];
  sol: number;
  camera: string;
  thumb: string | null;
  url: string | null;
  credit: string | null;
}

export interface TerrainTarget {
  id: string;
  name: string;
  position: [number, number];
}

interface Props {
  config: TerrainConfig;
  /** Site reference elevation (m); the mesh is expressed relative to it. */
  referenceM: number;
  /** Zoom range served by the site's tiles. */
  zoomRange: [number, number];
  exaggeration: number;
  activeRoute: Route | null;
  targets: TerrainTarget[];
  /** Rover traverse lines. */
  traverse: [number, number][][];
  photos: TerrainPhoto[];
  profile: RouteProfile[];
  progressM: number;
  /** The flyover drives the camera. */
  following: boolean;
  /** A view to apply; a new object re-applies the same view. */
  preset: { name: ViewPreset } | null;
  /** The user moved the camera by hand. */
  onUserMove?: () => void;
}

const SKY = {
  "sky-color": "#b98a5e",
  "horizon-color": "#e7c39a",
  "fog-color": "#cf9f72",
  "sky-horizon-blend": 0.55,
  "horizon-fog-blend": 0.7,
  // Fog only toward the horizon: the site itself keeps its true colours.
  "fog-ground-blend": 0.97,
  "atmosphere-blend": 0.6,
} as const;

function routeData(route: Route | null): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: route ? [{ type: "Feature", properties: {}, geometry: route.geometry as GeoJSON.LineString }] : [],
  };
}

function buildStyle(config: TerrainConfig, referenceM: number, zoomRange: [number, number]): StyleSpecification {
  const [minzoom, maxzoom] = zoomRange;
  const bounds = config.bbox;
  // No `bounds` here: tiles around the site come back flat from the protocol, so the
  // mesh and its shading continue past the site's edges.
  const dem = {
    type: "raster-dem" as const,
    tiles: [demTileUrl(referenceM, bounds, config.elevationUrlTemplate)],
    encoding: "mapbox" as const,
    tileSize: 256,
    minzoom,
    maxzoom,
  };
  const [w, s, e, n] = bounds;
  return {
    version: 8,
    sources: {
      // Separate sources for the mesh and the shading, as MapLibre recommends.
      terrain: dem,
      shade: dem,
      imagery: { type: "raster", tiles: [config.textureUrlTemplate], tileSize: 256, minzoom, maxzoom, bounds },
      // The iron-oxide wash covers the site and the plain around it alike, so the site
      // does not read as a slab laid on a different ground.
      plain: {
        type: "geojson",
        data: {
          type: "Polygon",
          coordinates: [[[w - 1, s - 1], [e + 1, s - 1], [e + 1, n + 1], [w - 1, n + 1], [w - 1, s - 1]]],
        },
      },
      route: { type: "geojson", data: routeData(null) },
      traverse: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
    },
    layers: [
      // Bare regolith beyond the imagery: the imagery's mean tone, so the edge fades out.
      { id: "ground", type: "background", paint: { "background-color": "#9e9e9e" } },
      { id: "imagery", type: "raster", source: "imagery", paint: { "raster-contrast": 0.12, "raster-fade-duration": 200 } },
      { id: "oxide", type: "fill", source: "plain", paint: { "fill-color": "#a4552b", "fill-opacity": 0.34 } },
      {
        id: "relief",
        type: "hillshade",
        source: "shade",
        paint: {
          "hillshade-method": "multidirectional",
          "hillshade-exaggeration": 0.65,
          "hillshade-shadow-color": "#3d2617",
          "hillshade-highlight-color": "#ffd9ad",
          "hillshade-accent-color": "#3a2214",
        },
      },
      {
        id: "traverse",
        type: "line",
        source: "traverse",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": "#f0e442",
          "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1.5, 18, 5],
          "line-dasharray": [2, 1.5],
          "line-opacity": 0.9,
        },
      },
      {
        id: "route-casing",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#fbf4ea", "line-width": ["interpolate", ["linear"], ["zoom"], 13, 6, 18, 16], "line-opacity": 0.9 },
      },
      {
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": colors.route.safest, "line-width": ["interpolate", ["linear"], ["zoom"], 13, 3.5, 18, 10] },
      },
    ],
    terrain: { source: "terrain", exaggeration: 2 * MARS_TO_RENDER },
    sky: SKY,
  };
}

function targetElement(name: string): HTMLElement {
  const el = document.createElement("div");
  el.className = "pointer-events-none flex flex-col items-center";
  const label = document.createElement("span");
  label.textContent = name;
  label.className =
    "mb-1 whitespace-nowrap rounded-md border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 text-[11px] text-[var(--text)] backdrop-blur-md";
  const stem = document.createElement("span");
  stem.className = "h-5 w-px bg-[var(--text)] opacity-70";
  const dot = document.createElement("span");
  dot.className = "size-2.5 rounded-full border-2 border-[var(--text)] bg-[#56b4e9]";
  el.append(label, stem, dot);
  return el;
}

function photoElement(photo: TerrainPhoto): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.setAttribute("aria-label", `Rover image, sol ${photo.sol}, ${photo.camera}`);
  // Hundreds of images sit along the traverse: small dots that grow under the pointer,
  // inside a 24 px hit area so they stay easy to click.
  el.className = "group grid size-6 cursor-pointer place-items-center rounded-full";
  const dot = document.createElement("span");
  dot.className =
    "size-2.5 rounded-full border border-[#1a1310] bg-[#f0e442] shadow-[0_1px_3px_rgb(0_0_0/0.45)] transition-transform group-hover:scale-[1.8] group-focus-visible:scale-[1.8]";
  el.append(dot);
  return el;
}

function photoPopup(photo: TerrainPhoto): HTMLElement {
  const box = document.createElement("div");
  box.className = "w-56 text-[var(--text)]";
  if (photo.thumb) {
    const img = document.createElement("img");
    img.src = photo.thumb;
    img.alt = `${photo.camera}, sol ${photo.sol}`;
    img.loading = "lazy";
    img.className = "mb-2 aspect-square w-full rounded-md bg-[var(--surface-2)] object-cover";
    box.append(img);
  } else {
    const none = document.createElement("p");
    none.textContent = "No thumbnail for this image.";
    none.className = "mb-2 text-xs text-[var(--text-muted)]";
    box.append(none);
  }
  const title = document.createElement("p");
  title.className = "text-[13px] font-medium";
  title.textContent = `Sol ${photo.sol} · ${photo.camera}`;
  const note = document.createElement("p");
  note.className = "mt-0.5 text-[11px] text-[var(--text-muted)]";
  note.textContent = `Rover position at time of capture${photo.credit ? ` · ${photo.credit}` : ""}`;
  box.append(title, note);
  if (photo.url) {
    const a = document.createElement("a");
    a.href = photo.url;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.textContent = "Full image ↗";
    a.className = "mt-1.5 inline-block text-xs underline";
    box.append(a);
  }
  return box;
}

function walkerElement(): HTMLElement {
  const el = document.createElement("div");
  el.className = "pointer-events-none size-4 rounded-full border-2 border-white bg-[#f3c48b] shadow-[0_0_0_6px_rgb(243_196_139/0.28)]";
  el.setAttribute("aria-hidden", "true");
  return el;
}

export function TerrainCanvas({
  config,
  referenceM,
  zoomRange,
  exaggeration,
  activeRoute,
  targets,
  traverse,
  photos,
  profile,
  progressM,
  following,
  preset,
  onUserMove,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const walkerRef = useRef<maplibregl.Marker | null>(null);
  const userMoveRef = useRef(onUserMove);
  userMoveRef.current = onUserMove;
  const [ready, setReady] = useState(false);
  const [drawn, setDrawn] = useState(false);

  // Map instance, per site.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    registerDemProtocol();
    const [w, s, e, n] = config.bbox;
    const padLon = (e - w) * 0.8;
    const padLat = (n - s) * 0.8;
    const map = new maplibregl.Map({
      container,
      style: buildStyle(config, referenceM, zoomRange),
      bounds: [w, s, e, n],
      fitBoundsOptions: { padding: 40 },
      pitch: 62,
      bearing: -24,
      maxPitch: 85,
      minZoom: 11,
      maxZoom: 19.5,
      maxBounds: [w - padLon, s - padLat, e + padLon, n + padLat],
      attributionControl: { compact: true, customAttribution: "Marswalk · Mars 2000" },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showZoom: true }), "bottom-right");
    map.on("load", () => setReady(true));
    map.once("idle", () => setDrawn(true));
    // Only gestures carry an originalEvent; programmatic moves (flyover) do not.
    map.on("movestart", (ev) => {
      if ((ev as { originalEvent?: Event }).originalEvent) userMoveRef.current?.();
    });
    mapRef.current = map;

    // The container may be laid out after mount (route change): track its size,
    // otherwise the canvas keeps its first, near-empty size.
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(container);

    return () => {
      ro.disconnect();
      walkerRef.current?.remove();
      walkerRef.current = null;
      map.remove();
      mapRef.current = null;
      setReady(false);
      setDrawn(false);
    };
  }, [config, referenceM, zoomRange]);

  // Exaggeration.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setTerrain({ source: "terrain", exaggeration: exaggeration * MARS_TO_RENDER });
  }, [exaggeration, ready]);

  // Route.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("route") as maplibregl.GeoJSONSource | undefined)?.setData(routeData(activeRoute));
    const color = (activeRoute && colors.route[activeRoute.variant]) || colors.route.safest;
    map.setPaintProperty("route-line", "line-color", color);
  }, [activeRoute, ready]);

  // Target markers.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const markers = targets.map((t) =>
      new maplibregl.Marker({ element: targetElement(t.name), anchor: "bottom" }).setLngLat(t.position).addTo(map),
    );
    return () => markers.forEach((m) => m.remove());
  }, [targets, ready]);

  // Rover traverse.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("traverse") as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: traverse.map((coordinates) => ({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates },
      })),
    });
  }, [traverse, ready]);

  // Rover images: a marker per image, its picture in a popup.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const markers = photos.map((p) => {
      const popup = new maplibregl.Popup({ offset: 16, maxWidth: "none", className: "mw-photo" }).setDOMContent(
        photoPopup(p),
      );
      return new maplibregl.Marker({ element: photoElement(p) }).setLngLat(p.position).setPopup(popup).addTo(map);
    });
    return () => markers.forEach((m) => m.remove());
  }, [photos, ready]);

  // Walker marker and chase camera.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (profile.length === 0 || progressM <= 0) {
      walkerRef.current?.remove();
      walkerRef.current = null;
      return;
    }
    const here = sampleProfile(profile, progressM).position;
    walkerRef.current ??= new maplibregl.Marker({ element: walkerElement() }).setLngLat(here).addTo(map);
    walkerRef.current.setLngLat(here);
    if (following) applyChaseCamera(map, profile, progressM);
  }, [profile, progressM, following, ready]);

  // Named views.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !preset) return;
    applyPreset(map, preset.name, config.bbox);
  }, [preset, ready, config.bbox]);

  // MapLibre forces `position: relative` on its container: the container fills a
  // positioned wrapper by size, not by insets, or it collapses to zero height.
  return (
    <div className="absolute inset-0 bg-[linear-gradient(#b98a5e,#e7c39a_55%,#5a3a27_56%)]">
      <div
        ref={containerRef}
        className="h-full w-full"
        // A region, not an image: it holds focusable content (canvas, markers, controls).
        role="region"
        aria-label="3D rendering of the Martian terrain"
        data-testid="terrain-canvas"
      />
      <div
        aria-hidden={drawn}
        className={`pointer-events-none absolute inset-0 grid place-items-center bg-[linear-gradient(#b98a5e,#e7c39a_55%,#5a3a27_56%)] transition-opacity duration-700 ${
          drawn ? "opacity-0" : "opacity-100"
        }`}
      >
        <p className="label-caps animate-pulse !text-[#2a1a10]">Building terrain…</p>
      </div>
    </div>
  );
}
