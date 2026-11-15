/**
 * Tests de F3, sur un plan réel du site fictif calculé par P3
 * (fixtures/plan-p3.json : POST /api/sites/fictif/plans, cibles T1, T2, T3).
 *
 * Critères d'acceptation :
 *   1. Survoler le profil déplace un repère sur la carte, et inversement.
 *   2. Les totaux du profil égalent ceux de la variante.
 * Livrables : bandes de pente, durée par tronçon, marqueurs des cibles.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import * as echarts from "echarts/core";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Plan, Route } from "@/shared/api/client";
import { distanceM } from "@/shared/geodesy";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { buildChartOption } from "./chartOption";
import planFixture from "./fixtures/plan-p3.json";
import { feature } from "./index";
import { buildProfileLayers, onRouteHover } from "./mapLayers";
import {
  compareTotals,
  formatDuration,
  nearestDistance,
  pointOfNoReturnM,
  positionAtDistance,
  profileTotals,
  sampleIndexAt,
  segmentSpans,
  selectProfileRoute,
  slopeBands,
  targetMarkers,
} from "./profileData";
import { ProfilePanel } from "./ProfilePanel";

const PLAN = planFixture as unknown as Plan;
const SAFEST = PLAN.routes.find((r) => r.variant === "safest")!;
const SCIENCE = PLAN.routes.find((r) => r.variant === "science")!;
const THRESHOLDS = {
  penaltyDeg: PLAN.settings.penalty_slope_deg,
  maxDeg: PLAN.settings.max_slope_deg,
};
const NAMES = { T1: "Front du delta", T2: "Bord des dunes", T3: "Cratère" };

function resetStore() {
  useShared.setState({
    siteId: "fictif",
    activePlanId: null,
    activeRouteId: null,
    hoverDistanceM: null,
  });
}

beforeEach(resetStore);
afterEach(cleanup);

// ---------------------------------------------------------------------------
// Calculs purs
// ---------------------------------------------------------------------------

describe("choix de l'itinéraire", () => {
  it("suit la variante active", () => {
    expect(selectProfileRoute(PLAN, SCIENCE.id)).toEqual({ route: SCIENCE, preview: false });
  });
  it("montre la plus sûre en aperçu quand aucune variante n'est choisie", () => {
    expect(selectProfileRoute(PLAN, null)).toEqual({ route: SAFEST, preview: true });
  });
  it("ignore selected_route_id tant que le plan n'est pas à l'état selected", () => {
    expect(PLAN.status).toBe("computed");
    expect(PLAN.selected_route_id).toBe(SAFEST.id);
    expect(selectProfileRoute(PLAN, null)?.preview).toBe(true);
  });
  it("revient à la variante retenue dans le plan", () => {
    const plan: Plan = { ...PLAN, status: "selected", selected_route_id: SCIENCE.id };
    expect(selectProfileRoute(plan, null)?.route.id).toBe(SCIENCE.id);
  });
  it("n'affiche rien sans plan", () => {
    expect(selectProfileRoute(undefined, null)).toBeNull();
  });
});

describe("totaux (acceptation 2)", () => {
  it.each(PLAN.routes.map((r) => [r.variant, r] as const))(
    "les totaux du profil égalent ceux de la variante %s",
    (_v, route) => {
      expect(compareTotals(route)).toEqual([]);
      const p = profileTotals(route);
      expect(p.distanceM).toBeCloseTo(route.totals.distance_m, 0);
      expect(p.durationS).toBeCloseTo(route.totals.duration_s, 0);
    },
  );

  it("signale un écart", () => {
    const broken: Route = { ...SAFEST, totals: { ...SAFEST.totals, duration_s: SAFEST.totals.duration_s + 600 } };
    expect(compareTotals(broken).map((m) => m.field)).toEqual(["durationS"]);
  });
});

describe("bandes de pente", () => {
  const profile = [0, 5, 10, 15, 20, 25, 30].map((d, i) => ({
    distance_m: d,
    position: [0, 0] as [number, number],
    elevation_m: 0,
    slope_deg: [2, 12, 14, 25, -22, 3, 11][i]!,
    time_s: d,
    segment_index: 0,
  }));

  it("regroupe les échantillons consécutifs par niveau", () => {
    expect(slopeBands(profile, { penaltyDeg: 10, maxDeg: 20 })).toEqual([
      { level: "caution", fromM: 5, toM: 15, maxSlopeDeg: 14 },
      { level: "danger", fromM: 15, toM: 25, maxSlopeDeg: 25 },
      { level: "caution", fromM: 30, toM: 30, maxSlopeDeg: 11 },
    ]);
  });

  it("trouve les pentes pénalisées du plan réel", () => {
    const bands = slopeBands(SAFEST.profile, THRESHOLDS);
    expect(bands.length).toBeGreaterThan(0);
    for (const b of bands) expect(b.maxSlopeDeg).toBeGreaterThanOrEqual(THRESHOLDS.penaltyDeg);
  });
});

describe("tronçons et cibles", () => {
  it("cumule les tronçons jusqu'à la distance totale", () => {
    const spans = segmentSpans(SAFEST, NAMES);
    expect(spans).toHaveLength(SAFEST.segments.length);
    expect(spans[0]!.fromLabel).toBe("Habitat");
    expect(spans[spans.length - 1]!.toLabel).toBe("Habitat");
    expect(spans[spans.length - 1]!.toM).toBeCloseTo(SAFEST.totals.distance_m, 0);
  });

  it("place un marqueur par cible visitée, dans l'ordre du plan", () => {
    const markers = targetMarkers(segmentSpans(SAFEST, NAMES));
    expect(markers.map((m) => m.targetId)).toEqual(
      SAFEST.segments.map((s) => s.to_target_id).filter(Boolean),
    );
    expect(markers[0]!.label).toBe(NAMES[markers[0]!.targetId as keyof typeof NAMES]);
  });

  it("n'affiche pas de point de non-retour quand il coïncide avec l'arrivée", () => {
    expect(pointOfNoReturnM(SAFEST)).toBeNull();
    const t = SAFEST.profile[200]!.time_s;
    const early: Route = { ...SAFEST, return_check: { ...SAFEST.return_check, point_of_no_return_time_s: t } };
    expect(pointOfNoReturnM(early)).toBe(SAFEST.profile[200]!.distance_m);
  });

  it("formate les durées", () => {
    expect(formatDuration(42)).toBe("42 s");
    expect(formatDuration(712)).toBe("12 min");
    expect(formatDuration(6401)).toBe("1 h 47");
    expect(formatDuration(3599)).toBe("1 h");
  });
});

describe("géométrie du survol", () => {
  it("interpole la position le long du profil", () => {
    const a = SAFEST.profile[10]!;
    const b = SAFEST.profile[11]!;
    const mid = positionAtDistance(SAFEST.profile, (a.distance_m + b.distance_m) / 2)!;
    expect(mid[0]).toBeCloseTo((a.position[0] + b.position[0]) / 2, 9);
    expect(sampleIndexAt(SAFEST.profile, a.distance_m + 0.1)).toBe(10);
  });

  it("retrouve la distance d'un point de la carte", () => {
    const s = SAFEST.profile[120]!;
    const hit = nearestDistance(SAFEST.profile, s.position)!;
    expect(hit.offsetM).toBeLessThan(1e-6);
    // Le premier passage l'emporte : la distance trouvée a la même position.
    expect(distanceM(positionAtDistance(SAFEST.profile, hit.distanceM)!, s.position)).toBeLessThan(1e-6);
  });
});

describe("option ECharts", () => {
  it("contient les bandes, les cibles, les durées et le repère externe", () => {
    const spans = segmentSpans(SAFEST, NAMES);
    const opt = buildChartOption({
      profile: SAFEST.profile,
      spans,
      bands: slopeBands(SAFEST.profile, THRESHOLDS),
      targets: targetMarkers(spans),
      pointOfNoReturnM: null,
      hoverDistanceM: 500,
      lineColor: "#009e73",
    }) as { series: { markArea: { data: { name?: string }[][] }; markLine?: { data: { name?: string; xAxis: number }[] } }[] };
    const [alt, slope] = opt.series;
    const bandNames = alt!.markArea.data.map((d) => d[0]!.name!);
    expect(bandNames.every((n) => /^(▲|⛔) \d+°$/.test(n))).toBe(true);
    const lineNames = alt!.markLine!.data.map((d) => d.name);
    expect(lineNames).toContain("◆ Front du delta");
    expect(alt!.markLine!.data.find((d) => d.name === "hover")?.xAxis).toBe(500);
    expect(slope!.markArea.data[0]![0]!.name).toBe(`1 · ${formatDuration(SAFEST.segments[0]!.duration_s)}`);
  });
});

// ---------------------------------------------------------------------------
// Synchronisation carte ↔ profil (acceptation 1)
// ---------------------------------------------------------------------------

describe("couches de carte", () => {
  it("place le repère à la distance survolée", () => {
    const layers = buildProfileLayers(PLAN, SAFEST.id, 600);
    const marker = layers.find((l) => l.id === "f3-hover-marker");
    expect(marker).toBeDefined();
    const data = marker!.props.data as { position: [number, number] }[];
    expect(data[0]!.position).toEqual(positionAtDistance(SAFEST.profile, 600));
  });

  it("pas de repère sans survol", () => {
    const ids = buildProfileLayers(PLAN, SAFEST.id, null).map((l) => l.id);
    expect(ids).toEqual(["f3-route-hover"]);
  });

  it("le survol de l'itinéraire sur la carte écrit hoverDistanceM, et sortir l'efface", () => {
    useShared.setState({ activeRouteId: SAFEST.id });
    const s = SAFEST.profile[150]!;
    onRouteHover(PLAN, { coordinate: s.position, object: {} });
    expect(useShared.getState().hoverDistanceM).toBe(s.distance_m);
    onRouteHover(PLAN, { coordinate: undefined, object: null });
    expect(useShared.getState().hoverDistanceM).toBeNull();
  });

  it("ignore un survol loin de l'itinéraire", () => {
    useShared.setState({ activeRouteId: SAFEST.id });
    const s = SAFEST.profile[150]!;
    onRouteHover(PLAN, { coordinate: [s.position[0] + 0.01, s.position[1]], object: {} });
    expect(useShared.getState().hoverDistanceM).toBeNull();
  });
});

function renderPanel(plan: Plan | null = PLAN) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.targets("fictif"), Object.entries(NAMES).map(([id, name]) => ({ id, name })));
  if (plan) {
    qc.setQueryData(queryKeys.plan(plan.id), plan);
    useShared.setState({ activePlanId: plan.id });
  }
  return render(
    <QueryClientProvider client={qc}>
      <ProfilePanel />
    </QueryClientProvider>,
  );
}

describe("panneau du profil", () => {
  it("est déclaré dans l'emplacement du bas", () => {
    expect(feature.panels).toEqual([expect.objectContaining({ slot: "bottom" })]);
    expect(feature.mapLayers).toBeTypeOf("function");
  });

  it("invite à ajouter des cibles sans plan", () => {
    renderPanel(null);
    expect(screen.getByText(/Ajoutez des cibles/)).toBeTruthy();
  });

  it("affiche les totaux de la variante et la durée de chaque tronçon", () => {
    useShared.setState({ activeRouteId: SAFEST.id });
    renderPanel();
    const totals = screen.getByTestId("profile-totals").textContent!;
    expect(totals).toContain(`Durée ${formatDuration(SAFEST.totals.duration_s)}`);
    expect(screen.getByTestId("totals-check").textContent).toContain("conformes");
    SAFEST.segments.forEach((s) => {
      expect(screen.getByTestId(`segment-${s.index}`).textContent).toContain(formatDuration(s.duration_s));
    });
    expect(screen.getByTestId("segment-0").textContent).toContain("Habitat → Front du delta");
    expect(screen.queryByText(/Aperçu/)).toBeNull();
  });

  it("signale l'aperçu quand aucune variante n'est choisie, sans en choisir une", () => {
    renderPanel();
    expect(screen.getByText(/Aperçu : aucune variante choisie/)).toBeTruthy();
    expect(useShared.getState().activeRouteId).toBeNull();
  });

  it("survoler le graphique écrit hoverDistanceM, que la carte suit", () => {
    useShared.setState({ activeRouteId: SAFEST.id });
    renderPanel();
    const chart = echarts.getInstanceByDom(screen.getByTestId("profile-chart"))!;
    expect(chart).toBeDefined();
    const target = SAFEST.profile[90]!;
    act(() => {
      (chart as unknown as { trigger: (n: string, e: unknown) => void }).trigger("updateaxispointer", {
        axesInfo: [{ axisDim: "x", value: target.distance_m + 1 }],
      });
    });
    const hover = useShared.getState().hoverDistanceM;
    expect(hover).toBe(target.distance_m);
    const marker = buildProfileLayers(PLAN, SAFEST.id, hover).find((l) => l.id === "f3-hover-marker")!;
    expect((marker.props.data as { position: [number, number] }[])[0]!.position).toEqual(target.position);
  });

  it("survoler une ligne du tableau déplace aussi le repère", () => {
    useShared.setState({ activeRouteId: SAFEST.id });
    renderPanel();
    fireEvent.mouseEnter(screen.getByTestId("segment-1"));
    const spans = segmentSpans(SAFEST);
    expect(useShared.getState().hoverDistanceM).toBeCloseTo((spans[1]!.fromM + spans[1]!.toM) / 2);
    expect(screen.getByTestId("segment-1").getAttribute("aria-current")).toBe("true");
    fireEvent.mouseLeave(screen.getByTestId("segment-1"));
    expect(useShared.getState().hoverDistanceM).toBeNull();
  });
});
