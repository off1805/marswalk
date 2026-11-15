/**
 * Carte de la coquille (T00) : MapLibre pour les tuiles, deck.gl par-dessus pour les couches
 * des fonctionnalités. Affiche l'imagerie de base du site ; F1 gère les autres couches.
 *
 * Règle R3 : les tuiles sont en WebMercatorQuad appliquée aux longitudes et latitudes
 * martiennes. La barre d'échelle native de MapLibre est désactivée ; toute mesure passe
 * par shared/geodesy.ts.
 */
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { MapContext, MapSourceSpec } from "./feature";
import { registry } from "./registry";
import { tileUrl, type SiteManifest } from "@/shared/api/client";
import { emitMapClick } from "@/shared/mapClick";
import { useShared } from "@/shared/store";

const BASE_LAYERS = ["hirise_vis", "ctx_vis", "hillshade"];

export function baseLayerOf(manifest: SiteManifest) {
  return (
    BASE_LAYERS.map((id) => manifest.layers.find((l) => l.id === id && l.tiles && l.status !== "missing")).find(
      Boolean,
    ) ?? null
  );
}

function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/**
 * Smallest zoom at which the site imagery covers the whole map: the camera can never show
 * the empty space around the site. Measured from the current projection of the bbox.
 */
function coverZoom(map: maplibregl.Map, bbox: SiteManifest["bbox"]): number {
  const [w, s, e, n] = bbox;
  const a = map.project([w, n]);
  const b = map.project([e, s]);
  const bw = Math.abs(b.x - a.x);
  const bh = Math.abs(b.y - a.y);
  const { clientWidth: cw, clientHeight: ch } = map.getContainer();
  if (!bw || !bh || !cw || !ch) return map.getMinZoom();
  return Math.min(20, map.getZoom() + Math.log2(Math.max(cw / bw, ch / bh)));
}

function baseStyle(manifest: SiteManifest): StyleSpecification {
  const base = baseLayerOf(manifest);
  const style: StyleSpecification = {
    version: 8,
    sources: {},
    layers: [{ id: "background", type: "background", paint: { "background-color": "#2a1a12" } }],
  };
  if (base?.tiles) {
    style.sources.base = {
      type: "raster",
      tiles: [tileUrl(manifest.site_id, base.id, base.tiles.format)],
      tileSize: base.tiles.tile_size ?? 256,
      minzoom: base.tiles.minzoom,
      maxzoom: base.tiles.maxzoom,
      bounds: manifest.bbox as [number, number, number, number],
      attribution: `${base.title} : ${base.source.instrument}`,
    };
    style.layers.push({ id: "base", type: "raster", source: "base", paint: { "raster-contrast": 0.08 } });
    // Iron-oxide wash over the greyscale orbital imagery, under every feature layer.
    style.layers.push({
      id: "mars-tint",
      type: "background",
      paint: { "background-color": cssVar("--mars-tint", "#a4552b"), "background-opacity": Number(cssVar("--mars-tint-opacity", "0.3")) },
    });
  }
  return style;
}

function syncSources(map: maplibregl.Map, specs: MapSourceSpec[], owned: Set<string>) {
  const wanted = new Set(specs.map((s) => s.id));
  for (const id of owned) {
    if (wanted.has(id)) continue;
    for (const layer of map.getStyle().layers ?? []) {
      if ("source" in layer && layer.source === id) map.removeLayer(layer.id);
    }
    if (map.getSource(id)) map.removeSource(id);
    owned.delete(id);
  }
  for (const spec of specs) {
    if (!map.getSource(spec.id)) map.addSource(spec.id, spec.source);
    for (const layer of spec.layers) {
      if (!map.getLayer(layer.id)) map.addLayer(layer);
      else if (layer.type !== "background" && "paint" in layer && layer.paint) {
        for (const [k, v] of Object.entries(layer.paint)) map.setPaintProperty(layer.id, k, v);
      }
      if (layer.layout?.visibility) map.setLayoutProperty(layer.id, "visibility", layer.layout.visibility);
    }
    owned.add(spec.id);
  }
}

export function MapView({ manifest }: { manifest: SiteManifest }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const ownedSources = useRef(new Set<string>());
  const [zoom, setZoom] = useState(14);
  const [ready, setReady] = useState(false);
  const state = useShared();

  useEffect(() => {
    if (!container.current) return;
    const [w, s, e, n] = manifest.bbox;
    const map = new maplibregl.Map({
      container: container.current,
      style: baseStyle(manifest),
      bounds: [w, s, e, n],
      // The site fills the view edge to edge; the camera stays over the imagery.
      maxBounds: [w, s, e, n],
      minZoom: 0,
      maxZoom: 20,
      attributionControl: { compact: true, customAttribution: "Marswalk · Mars 2000" },
    });
    const fitCover = () => {
      map.setMinZoom(null);
      const z = coverZoom(map, manifest.bbox);
      map.setMinZoom(z);
      if (map.getZoom() < z) map.jumpTo({ zoom: z });
    };
    fitCover();
    map.on("resize", fitCover);
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay);
    map.on("zoomend", () => setZoom(map.getZoom()));
    map.on("click", (e) => emitMapClick({ lon: e.lngLat.lng, lat: e.lngLat.lat }));
    map.on("load", () => setReady(true));
    mapRef.current = map;
    overlayRef.current = overlay;
    const owned = ownedSources.current;
    return () => {
      owned.clear();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
      setReady(false);
    };
  }, [manifest]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const ctx: MapContext = { siteId: manifest.site_id, manifest, zoom, state };
    const specs = registry.flatMap((f) =>
      typeof f.mapSources === "function" ? f.mapSources(ctx) : (f.mapSources ?? []),
    );
    syncSources(map, specs, ownedSources.current);
    overlayRef.current?.setProps({ layers: registry.flatMap((f) => f.mapLayers?.(ctx) ?? []) });
  }, [manifest, zoom, state, ready]);

  return <div ref={container} className="h-full w-full" data-testid="map" aria-label="Site map" />;
}
