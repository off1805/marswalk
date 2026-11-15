/**
 * Tests de la feature F2 — cibles et itinéraire.
 *
 * Critères couverts :
 *   1. Ajout d'une cible → POST /api/sites/{siteId}/targets appelé.
 *   2. Déplacement d'une cible → PATCH /api/targets/{id} appelé.
 *   3. Suppression d'une cible → DELETE /api/targets/{id} appelé.
 *   4. Un seul POST de plan après plusieurs modifications rapides (debounce de 400 ms).
 *   5. Les trois variantes s'affichent dans le comparateur.
 *   6. La sélection d'une variante appelle PATCH /api/plans/{id}.
 */

import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
} from "vitest";
import {
  render,
  screen,
  waitFor,
  act,
  fireEvent,
  cleanup,
} from "@testing-library/react";
import { renderHook, act as actHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";

import { useShared } from "@/shared/store";
import type { Target, Plan, Route } from "@/shared/api/client";
import { RouteComparator } from "./RouteComparator";
import { injectQueryClient } from "./index";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const BASE_TARGET: Target = {
  id: "T1",
  site_id: "fictif",
  name: "Front du delta",
  kind: "science",
  position: [77.5844444, 18.392131],
  objective: "Argiles et carbonates du delta",
  measurement: "Imagerie rapprochée et prélèvement",
  work_time_s: 1200,
  priority: 1,
  created_at: "2026-11-14T10:00:00Z",
  updated_at: "2026-11-14T10:00:00Z",
};

const TARGET_2: Target = {
  ...BASE_TARGET,
  id: "T2",
  name: "Bord des dunes",
  position: [77.5725334, 18.3774535],
  priority: 2,
};

function makeRoute(id: string, variant: Route["variant"]): Route {
  return {
    id,
    variant,
    geometry: {
      type: "LineString",
      coordinates: [
        [77.5782222, 18.3816712],
        [77.5844444, 18.392131],
      ],
    },
    segments: [
      {
        index: 0,
        from_point: [77.5782222, 18.3816712],
        to_point: [77.5844444, 18.392131],
        from_target_id: null,
        to_target_id: "T1",
        distance_m: 1200,
        duration_s: 1200,
        ascent_m: 10,
        descent_m: 0,
        max_slope_deg: 8,
        consumption: {
          oxygen_kg: 0.1,
          battery_wh: 20,
          water_l: 0.05,
          dose_usv: 5,
        },
        work_time_s: 1200,
      },
    ],
    profile: [],
    totals: {
      distance_m: 1200,
      walk_time_s: 1200,
      work_time_s: 1200,
      duration_s: 2400,
      ascent_m: 10,
      descent_m: 0,
      max_slope_deg: 8,
      consumption: {
        oxygen_kg: 0.1,
        battery_wh: 20,
        water_l: 0.05,
        dose_usv: 5,
      },
    },
    return_check: {
      status: "ok",
      reserve_at_return_pct: 60,
      limiting_consumable: "oxygen",
      point_of_no_return: null,
      point_of_no_return_time_s: null,
      targets_to_cut: [],
      message: null,
    },
    explanation: [
      { segment_index: 0, reasons: ["bouchon T00 : ligne droite"] },
    ],
    warnings: [],
  };
}

const MOCK_PLAN: Plan = {
  id: "plan-demo",
  site_id: "fictif",
  name: "Plan de démonstration",
  status: "computed",
  created_at: "2026-11-14T10:00:00Z",
  departure_utc: null,
  start: [77.5782222, 18.3816712],
  return_to: [77.5782222, 18.3816712],
  target_ids: ["T1"],
  settings: {
    preset: "standard",
    max_slope_deg: 20,
    penalty_slope_deg: 10,
    max_roughness_m: 0.5,
    obstacle_buffer_m: 2,
    scarp_buffer_m: 10,
    avoid_loose_soil_class: 3,
    require_radio: false,
    radio_penalty: 2,
    min_illumination: 0,
    min_reserve_pct: 30,
    max_dust_tau: 2,
    max_dose_usv: 1000,
    degraded_margin_pct: 15,
    weights: { time: 1, risk: 1, science: 0.5 },
  },
  suit: {
    name: "default",
    mass_total_kg: 180,
    gravity_ms2: 3.721,
    base_speed_mps: 1,
    max_speed_mps: 1.4,
    oxygen_capacity_kg: 1.2,
    oxygen_rate_kg_h: 0.08,
    battery_capacity_wh: 1500,
    battery_rate_w: 150,
    water_capacity_l: 4,
    water_rate_l_h: 0.3,
  },
  routes: [
    makeRoute("route-safest", "safest"),
    makeRoute("route-fastest", "fastest"),
    makeRoute("route-science", "science"),
  ],
  selected_route_id: null,
  compute_time_ms: 120,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function Wrapper({
  children,
  client,
}: {
  children: React.ReactNode;
  client: QueryClient;
}) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  useShared.setState({
    siteId: "fictif",
    activePlanId: null,
    activeRouteId: null,
    selectedTargetId: null,
    pickMode: "none",
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
  useShared.setState({
    activePlanId: null,
    activeRouteId: null,
    selectedTargetId: null,
    pickMode: "none",
  });
});

// ── 1. Ajout d'une cible ──────────────────────────────────────────────────────

describe("Ajout d'une cible", () => {
  it("appelle POST /api/sites/{siteId}/targets via useCreateTarget", async () => {
    // Mock api.POST directly — openapi-fetch can't parse relative URLs in jsdom
    const { api } = await import("@/shared/api/client");
    const newTarget: Target = { ...BASE_TARGET, id: "T-new", name: "Nouvelle cible" };
    const postSpy = vi.spyOn(api, "POST").mockResolvedValue({
      data: newTarget,
      error: undefined,
      response: new Response(),
    } as Awaited<ReturnType<typeof api.POST>>);

    const qc = makeQC();
    injectQueryClient(qc);

    const { useCreateTarget } = await import("./useTargets");
    const { result } = renderHook(() => useCreateTarget(), {
      wrapper: ({ children }) => <Wrapper client={qc}>{children}</Wrapper>,
    });

    const created = await actHook(async () =>
      result.current.mutateAsync({
        name: "Nouvelle cible",
        position: [77.58, 18.38] as [number, number],
        kind: "science" as const,
        priority: 1,
        work_time_s: 900,
      }),
    );

    expect(postSpy).toHaveBeenCalledWith(
      "/api/sites/{site_id}/targets",
      expect.objectContaining({ params: { path: { site_id: "fictif" } } }),
    );
    expect(created.id).toBe("T-new");
  });
});

// ── 2. Déplacement d'une cible ────────────────────────────────────────────────

describe("Déplacement d'une cible", () => {
  it("appelle PATCH /api/targets/{id} avec la nouvelle position", async () => {
    const { api } = await import("@/shared/api/client");
    const patchSpy = vi.spyOn(api, "PATCH").mockResolvedValue({
      data: { ...BASE_TARGET, position: [77.59, 18.40] },
      error: undefined,
      response: new Response(),
    } as Awaited<ReturnType<typeof api.PATCH>>);

    const qc = makeQC();
    const { useUpdateTarget } = await import("./useTargets");
    const { result } = renderHook(() => useUpdateTarget(), {
      wrapper: ({ children }) => <Wrapper client={qc}>{children}</Wrapper>,
    });

    await actHook(async () =>
      result.current.mutateAsync({ id: "T1", position: [77.59, 18.40] }),
    );

    expect(patchSpy).toHaveBeenCalledWith(
      "/api/targets/{target_id}",
      expect.objectContaining({ params: { path: { target_id: "T1" } } }),
    );
  });
});

// ── 3. Suppression d'une cible ────────────────────────────────────────────────

describe("Suppression d'une cible", () => {
  it("appelle DELETE /api/targets/{id}", async () => {
    const { api } = await import("@/shared/api/client");
    const deleteSpy = vi.spyOn(api, "DELETE").mockResolvedValue({
      data: undefined,
      error: undefined,
      response: new Response(null, { status: 204 }),
    } as Awaited<ReturnType<typeof api.DELETE>>);

    const qc = makeQC();
    const { useDeleteTarget } = await import("./useTargets");
    const { result } = renderHook(() => useDeleteTarget(), {
      wrapper: ({ children }) => <Wrapper client={qc}>{children}</Wrapper>,
    });

    await actHook(async () => result.current.mutateAsync("T1"));

    expect(deleteSpy).toHaveBeenCalledWith(
      "/api/targets/{target_id}",
      expect.objectContaining({ params: { path: { target_id: "T1" } } }),
    );
  });
});

// ── 4. Debounce : un seul POST de plan après plusieurs modifications rapides ──

describe("Debounce du recalcul automatique", () => {
  it(
    "n'envoie qu'un seul POST /api/sites/{siteId}/plans après deux modifications rapides",
    async () => {
      vi.useFakeTimers();

      const { api } = await import("@/shared/api/client");
      let postCallCount = 0;
      const postSpy = vi.spyOn(api, "POST").mockImplementation(async () => {
        postCallCount++;
        return {
          data: MOCK_PLAN,
          error: undefined,
          response: new Response(),
        } as Awaited<ReturnType<typeof api.POST>>;
      });

      const qc = makeQC();
      injectQueryClient(qc);

      const { useAutoPlan } = await import("./useAutoPlan");

      const { rerender } = renderHook(
        ({ targets }: { targets: Target[] }) => useAutoPlan(targets),
        {
          initialProps: { targets: [BASE_TARGET] },
          wrapper: ({ children }) => <Wrapper client={qc}>{children}</Wrapper>,
        },
      );

      // Deux modifications rapides (< 400 ms entre elles)
      actHook(() => {
        rerender({ targets: [{ ...BASE_TARGET, position: [77.59, 18.39] }] });
      });
      actHook(() => {
        rerender({ targets: [{ ...BASE_TARGET, position: [77.60, 18.40] }] });
      });

      // Avancer le debounce
      await actHook(async () => {
        vi.advanceTimersByTime(500);
      });

      // Laisser les promesses se résoudre
      await actHook(async () => {
        await Promise.resolve();
      });

      expect(postSpy).toHaveBeenCalledTimes(1);
      expect(postCallCount).toBe(1);

      vi.useRealTimers();
      postSpy.mockRestore();
    },
    { timeout: 10_000 },
  );
});

// ── 5. Les trois variantes s'affichent dans le comparateur ───────────────────

describe("RouteComparator", () => {
  it("affiche les trois variantes safest, fastest, science", () => {
    const qc = makeQC();
    render(
      <Wrapper client={qc}>
        <RouteComparator plan={MOCK_PLAN} />
      </Wrapper>,
    );

    expect(screen.getByRole("article", { name: /safest/i })).toBeTruthy();
    expect(screen.getByRole("article", { name: /fastest/i })).toBeTruthy();
    expect(screen.getByRole("article", { name: /science/i })).toBeTruthy();
  });

  it("n'en sélectionne aucune automatiquement", () => {
    const qc = makeQC();
    render(
      <Wrapper client={qc}>
        <RouteComparator plan={MOCK_PLAN} />
      </Wrapper>,
    );
    // No card should display the "Selected" badge
    expect(screen.queryByText("Selected")).toBeNull();
  });
});

// ── 6. Sélection d'une variante → PATCH /api/plans/{id} ──────────────────────

describe("Sélection d'une variante", () => {
  it("appelle PATCH /api/plans/{id} avec selected_route_id", async () => {
    const { api } = await import("@/shared/api/client");
    const patchSpy = vi.spyOn(api, "PATCH").mockResolvedValue({
      data: { ...MOCK_PLAN, selected_route_id: "route-safest" },
      error: undefined,
      response: new Response(),
    } as Awaited<ReturnType<typeof api.PATCH>>);

    const qc = makeQC();
    qc.setQueryData(["plans", "plan-demo"], MOCK_PLAN);
    useShared.setState({ activePlanId: "plan-demo", activeRouteId: null });

    render(
      <Wrapper client={qc}>
        <RouteComparator plan={MOCK_PLAN} />
      </Wrapper>,
    );

    // All three "Select this variant" buttons can be found by text
    const buttons = screen.getAllByText(/Select this variant/i);
    expect(buttons.length).toBe(3);

    await act(async () => {
      fireEvent.click(buttons[0]!);
    });

    await waitFor(() =>
      expect(patchSpy).toHaveBeenCalledWith(
        "/api/plans/{plan_id}",
        expect.objectContaining({
          body: expect.objectContaining({ selected_route_id: "route-safest" }),
        }),
      ),
    );
  });
});

// ── 7. TargetsPanel : liste des cibles visible ────────────────────────────────

describe("TargetsPanel", () => {
  it("affiche la liste des cibles pré-chargées", async () => {
    const { api } = await import("@/shared/api/client");
    // Stub all API calls that TargetsPanel triggers
    vi.spyOn(api, "GET").mockResolvedValue({
      data: [BASE_TARGET, TARGET_2],
      error: undefined,
      response: new Response(),
    } as Awaited<ReturnType<typeof api.GET>>);

    const qc = makeQC();
    qc.setQueryData(["sites", "fictif", "targets"], [BASE_TARGET, TARGET_2]);
    qc.setQueryData(["sites", "fictif", "hazards", "safety"], {
      type: "FeatureCollection",
      features: [],
      crs_note: "IAU_2015:49900",
    });
    injectQueryClient(qc);

    const { TargetsPanel } = await import("./TargetsPanel");
    render(
      <Wrapper client={qc}>
        <TargetsPanel />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(screen.getByRole("list", { name: "Target list" })).toBeTruthy(),
    );
    expect(screen.getByText("Front du delta")).toBeTruthy();
    expect(screen.getByText("Bord des dunes")).toBeTruthy();
  });
});
