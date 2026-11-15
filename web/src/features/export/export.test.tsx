import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import exportPlan from "@contracts/examples/export_plan.json";
import logbook from "@contracts/examples/logbook.json";
import plan from "@contracts/examples/plan.json";
import { feature } from ".";
import {
  formatDistance,
  formatDuration,
  logbookToGeojson,
  planView,
  profilePath,
  scaleBarMeters,
  type Logbook,
} from "./format";
import { LogbookSheet } from "./LogbookSheet";
import { PlanSheet } from "./PlanSheet";
import { api, type LonLat, type Plan } from "@/shared/api/client";

const book = logbook as unknown as Logbook;
const demoPlan = plan as unknown as Plan;

describe("mise en forme", () => {
  it("écrit les durées et distances en clair", () => {
    expect(formatDuration(45)).toBe("45 s");
    expect(formatDuration(720)).toBe("12 min");
    expect(formatDuration(5770)).toBe("1 h 36 min");
    expect(formatDuration(7200)).toBe("2 h");
    expect(formatDistance(640.4)).toBe("640 m");
    expect(formatDistance(2470.25)).toBe("2.47 km");
  });

  it("met le carnet en GeoJSON, un point par entrée positionnée", () => {
    const fc = logbookToGeojson(book);
    const features = fc.features ?? [];
    const positioned = book.entries.filter((e) => e.position);
    expect(fc.type).toBe("FeatureCollection");
    expect(features).toHaveLength(positioned.length);
    const f = features[0]!;
    expect(f.geometry).toEqual({ type: "Point", coordinates: positioned[0]!.position });
    expect(f.properties).toMatchObject({ sol: positioned[0]!.sol, lmst: positioned[0]!.lmst });
    for (const g of features)
      for (const v of Object.values(g.properties ?? {})) expect(v === null || typeof v !== "object").toBe(true);
  });

  it("dessine le plan à l'échelle, nord en haut", () => {
    const route = demoPlan.routes[0]!;
    const pts = route.geometry.coordinates as LonLat[];
    const view = planView(pts, 640, 420);
    for (const p of pts) {
      const [x, y] = view.project(p);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(640);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(420);
    }
    // Le point le plus au nord est le plus haut à l'écran.
    const north = pts.reduce((a, b) => (b[1] > a[1] ? b : a));
    expect(Math.min(...pts.map((p) => view.project(p)[1]))).toBeCloseTo(view.project(north)[1]);
    const bar = scaleBarMeters(view.scale);
    expect(bar * view.scale).toBeLessThanOrEqual(120);
    expect([1, 2, 5]).toContain(bar / 10 ** Math.floor(Math.log10(bar)));
  });

  it("trace le profil seulement quand l'altitude est connue", () => {
    expect(profilePath([], 640, 180)).toBeNull();
    const samples = [0, 100, 200].map((d, i) => ({
      distance_m: d,
      position: [77.58, 18.38] as LonLat,
      elevation_m: -2500 + i * 10,
      slope_deg: 2,
      time_s: d,
      segment_index: 0,
    }));
    const p = profilePath(samples, 640, 180)!;
    expect(p.d.startsWith("M")).toBe(true);
    expect(p.maxElevation - p.minElevation).toBe(20);
  });
});

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/export/plan/:planId" element={<PlanSheet />} />
          <Route path="/export/logbook/:evaId" element={<LogbookSheet />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("fiches imprimables", () => {
  beforeEach(() => {
    vi.spyOn(api, "GET").mockImplementation((async (path: string) => {
      const data: Record<string, unknown> = {
        "/api/plans/{plan_id}": plan,
        "/api/plans/{plan_id}/export.geojson": exportPlan,
        "/api/eva/{eva_id}/logbook": logbook,
      };
      return { data: data[path], error: undefined, response: new Response() };
    }) as never);
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("la fiche du plan montre carte, profil et un tableau des tronçons", async () => {
    renderAt("/export/plan/plan-demo");
    expect(await screen.findByRole("heading", { name: /EVA plan Sortie de démonstration/ })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Route map" })).toBeTruthy();
    const rows = screen.getByRole("table").querySelectorAll("tbody tr");
    expect(rows).toHaveLength(demoPlan.routes[0]!.segments.length);
    expect(rows[0]!.textContent).toContain("Front du delta");
    expect(screen.getByRole("button", { name: /Print/ })).toBeTruthy();
  });

  it("le carnet liste chaque entrée en sol et heure locale", async () => {
    renderAt("/export/logbook/eva-demo");
    expect(await screen.findByRole("heading", { name: /Field logbook/ })).toBeTruthy();
    const rows = screen.getByRole("table").querySelectorAll("tbody tr");
    expect(rows).toHaveLength(book.entries.length);
    expect(rows[0]!.textContent).toContain(book.entries[0]!.lmst);
    expect(screen.getByText(book.entries.find((e) => e.kind === "observation")!.text)).toBeTruthy();
  });
});

describe("fonctionnalité", () => {
  it("ajoute un panneau à droite et deux pages imprimables", () => {
    expect(feature.panels.map((p) => p.slot)).toEqual(["right"]);
    expect(feature.routes.map((r) => r.path)).toEqual(["/export/plan/:planId", "/export/logbook/:evaId"]);
  });
});
