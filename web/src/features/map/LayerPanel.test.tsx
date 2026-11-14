import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LayerPanel } from "./components/LayerPanel";
import { MarsScaleBar } from "./components/MarsScaleBar";
import { useShared } from "@/shared/store";
import { getMapSources } from "./sources";
import type { MapContext } from "@/app/feature";
import type { SiteManifest } from "@/shared/api/client";

const mockManifest: SiteManifest = {
  schema_version: "1.0",
  site_id: "fictif",
  name: "Site fictif (Jezero)",
  bbox: [77.56, 18.36, 77.59, 18.39],
  analysis_crs: "+proj=eqc +lat_ts=18.38 +lon_0=77.58 +R=3396190 +units=m +no_defs",
  grid: {
    resolution_m: 2.0,
    width: 1000,
    height: 1000,
    transform: [2.0, 0.0, -1000.0, 0.0, -2.0, 1090468.0],
  },
  habitat: [77.578, 18.381],
  rover: [77.581, 18.38],
  mission_epoch_utc: "2026-11-01T00:00:00Z",
  default_preset: "safety",
  layers: [
    {
      id: "slope",
      title: "Pente",
      kind: "derived",
      unit: "deg",
      source: { instrument: "SYNTHETIC", mission: "Marswalk" },
      tiles: {
        path: "tiles/slope/{z}/{x}/{y}.webp",
        minzoom: 12,
        maxzoom: 17,
        format: "webp",
        tile_size: 256,
      },
      status: "ok",
    },
    {
      id: "roughness",
      title: "Rugosité",
      kind: "derived",
      unit: "m",
      source: { instrument: "SYNTHETIC", mission: "Marswalk" },
      tiles: {
        path: "tiles/roughness/{z}/{x}/{y}.webp",
        minzoom: 12,
        maxzoom: 17,
        format: "webp",
        tile_size: 256,
      },
      status: "degraded",
    },
    {
      id: "hirise_vis",
      title: "Imagerie HiRISE",
      kind: "imagery",
      unit: "DN",
      source: { instrument: "HiRISE", mission: "MRO" },
      tiles: {
        path: "tiles/hirise_vis/{z}/{x}/{y}.webp",
        minzoom: 12,
        maxzoom: 19,
        format: "webp",
        tile_size: 256,
      },
      status: "ok",
    },
  ],
};

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Fonctionnalité Carte et couches (F1)", () => {
  beforeEach(() => {
    useShared.setState({
      siteId: "fictif",
      layers: {
        slope: { visible: true, opacity: 0.6 },
        roughness: { visible: false, opacity: 1.0 },
      },
      preset: "safety",
    });
  });

  it("génère les sources MapLibre pour les couches visibles", () => {
    const ctx: MapContext = {
      siteId: "fictif",
      manifest: mockManifest,
      zoom: 14,
      state: useShared.getState(),
    };

    const sources = getMapSources(ctx);
    expect(sources.length).toBe(1);
    expect(sources[0].id).toBe("raster-slope");
    expect(sources[0].layers[0].paint?.["raster-opacity"]).toBe(0.6);
  });

  it("affiche l'échelle martienne calculée sur Mars 2000 (R3)", () => {
    renderWithClient(<MarsScaleBar zoom={14} />);
    const scaleBar = screen.getByTestId("mars-scale-bar");
    expect(scaleBar).toBeDefined();
    expect(scaleBar.textContent).toContain("Mars 2000");
  });

  it("permet de basculer la visibilité d'une couche", () => {
    const setLayer = useShared.getState().setLayer;
    setLayer("slope", { visible: false });
    expect(useShared.getState().layers["slope"].visible).toBe(false);

    setLayer("roughness", { visible: true, opacity: 0.8 });
    expect(useShared.getState().layers["roughness"].visible).toBe(true);
    expect(useShared.getState().layers["roughness"].opacity).toBe(0.8);
  });
});
