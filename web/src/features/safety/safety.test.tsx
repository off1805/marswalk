import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import alertsExample from "@contracts/examples/alerts.json";
import conditionsExample from "@contracts/examples/conditions_current.json";
import evaExample from "@contracts/examples/eva.json";
import forecastExample from "@contracts/examples/conditions_forecast.json";
import planExample from "@contracts/examples/plan.json";
import scenariosExample from "@contracts/examples/scenarios.json";
import settingsExample from "@contracts/examples/settings.json";
import timeExample from "@contracts/examples/time.json";
import wsAlert from "@contracts/examples/ws_alert.json";
import wsAlertCleared from "@contracts/examples/ws_alert_cleared.json";
import wsBudget from "@contracts/examples/ws_budget.json";
import wsConditions from "@contracts/examples/ws_conditions.json";
import wsTelemetry from "@contracts/examples/ws_telemetry.json";
import { feature } from ".";
import { AlertBanner } from "./AlertBanner";
import { ConditionsPanel } from "./ConditionsPanel";
import { SafetyPanel } from "./SafetyPanel";
import { useSafety } from "./safetyStore";
import { ThresholdsPanel } from "./ThresholdsPanel";
import {
  advanceClock,
  consumableLevel,
  daylightLeftS,
  daylightLevel,
  doseLevel,
  doseRateLevel,
  dustLevel,
  formatCountdown,
  MARS_HOUR_S,
  parseLmst,
  pnrLevel,
  sortAlerts,
  validateSettings,
} from "./thresholds";
import { applyMessage } from "./useSafetyStream";
import { api, type Alert, type SafetySettings, type WsMessage } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";

const settings = settingsExample as SafetySettings;
const alerts = alertsExample as unknown as Alert[];

// --- Faux WebSocket -----------------------------------------------------------------
class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  closed = false;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
  }
  open() {
    this.onopen?.();
  }
  emit(msg: unknown) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
}

// --- Faux serveur -------------------------------------------------------------------
type Handler = (opts: { params?: { path?: Record<string, string> }; body?: unknown }) => unknown;
let getData: Record<string, unknown>;
let postSpy: ReturnType<typeof vi.fn>;
let putSpy: ReturnType<typeof vi.fn>;

function mockApi() {
  getData = {
    "/api/alerts": [],
    "/api/sites/{site_id}/conditions/current": conditionsExample,
    "/api/sites/{site_id}/conditions/forecast": forecastExample,
    "/api/sites/{site_id}/settings": settingsExample,
    "/api/time": timeExample,
    "/api/eva/{eva_id}": evaExample,
    "/api/plans/{plan_id}": planExample,
    "/api/scenarios": scenariosExample,
  };
  vi.spyOn(api, "GET").mockImplementation((async (path: string) => {
    const data = getData[path];
    return data === undefined ? { error: { detail: "inconnu" } } : { data: structuredClone(data) };
  }) as never);
  postSpy = vi.fn((path: string, opts: Parameters<Handler>[0]) => {
    if (path === "/api/alerts/{alert_id}/ack") {
      const a = alerts.find((x) => x.id === opts.params?.path?.alert_id) ?? alerts[0]!;
      return { data: { ...a, acknowledged: true, acknowledged_at: "2026-11-14T10:00:05Z" } };
    }
    if (path === "/api/eva") return { data: evaExample };
    return { data: { running: true, scenario_id: "solar-event", eva_id: "eva-demo", speed: 10 } };
  });
  vi.spyOn(api, "POST").mockImplementation((async (path: string, opts: never) => postSpy(path, opts)) as never);
  putSpy = vi.fn((_path: string, opts: { body: unknown }) => ({ data: opts.body }));
  vi.spyOn(api, "PUT").mockImplementation((async (path: string, opts: never) => putSpy(path, opts)) as never);
}

let client: QueryClient;
function wrap(node: ReactNode) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

beforeEach(() => {
  FakeSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  mockApi();
  useShared.setState({ siteId: "fictif", evaId: null, activePlanId: null, activeRouteId: null });
  useSafety.getState().reset();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

// --- Règles pures -------------------------------------------------------------------
describe("niveaux et seuils (alignés sur A3)", () => {
  it("consommables et réserve : attention sous minimum + 10 points, danger sous le minimum", () => {
    expect(consumableLevel(82, settings)).toBe("ok");
    expect(consumableLevel(39, settings)).toBe("caution");
    expect(consumableLevel(29, settings)).toBe("danger");
  });

  it("dose, débit de dose et poussière montent vers le danger", () => {
    expect(doseLevel(100, settings)).toBe("ok");
    expect(doseLevel(800, settings)).toBe("caution");
    expect(doseLevel(1000, settings)).toBe("danger");
    expect(doseRateLevel(10)).toBe("ok");
    expect(doseRateLevel(30)).toBe("caution");
    expect(doseRateLevel(250)).toBe("danger");
    expect(dustLevel(0.6, settings)).toBe("ok");
    expect(dustLevel(1.7, settings)).toBe("caution");
    expect(dustLevel(2.1, settings)).toBe("danger");
  });

  it("point de non-retour et coucher du Soleil", () => {
    expect(pnrLevel(5400)).toBe("ok");
    expect(pnrLevel(600)).toBe("caution");
    expect(pnrLevel(0)).toBe("danger");
    expect(pnrLevel(null)).toBe("ok");
    expect(daylightLeftS(17)).toBeCloseTo(MARS_HOUR_S);
    expect(daylightLevel(daylightLeftS(13.27))).toBe("ok");
    expect(daylightLevel(daylightLeftS(17.2))).toBe("caution");
    expect(daylightLevel(daylightLeftS(17.8))).toBe("danger");
  });

  it("classe les alertes : non acquittées, puis danger, attention, information", () => {
    const base = alerts[0]!;
    const list: Alert[] = [
      { ...base, id: "i", level: "info" },
      { ...base, id: "c", level: "caution" },
      { ...base, id: "d-ack", level: "danger", acknowledged: true },
      { ...base, id: "d", level: "danger" },
    ];
    expect(sortAlerts(list).map((a) => a.id)).toEqual(["d", "c", "i", "d-ack"]);
  });

  it("met les durées en clair", () => {
    expect(formatCountdown(5400)).toBe("1 h 30 min");
    expect(formatCountdown(605)).toBe("10 min 05 s");
    expect(formatCountdown(42)).toBe("42 s");
    expect(formatCountdown(-3)).toBe("dépassé");
    expect(formatCountdown(null)).toBe("—");
  });

  it("fait avancer l'horloge martienne à vitesse réelle, avec changement de sol", () => {
    const anchor = { utc: "2026-11-14T10:00:00Z", sol: 14, lmstHours: 23.9, receivedAt: 0 };
    const later = advanceClock(anchor, 0.2 * MARS_HOUR_S * 1000);
    expect(later.sol).toBe(15);
    expect(later.lmst).toBe("00:06:00");
    expect(later.utc.toISOString()).toBe(new Date(Date.parse(anchor.utc) + 0.2 * MARS_HOUR_S * 1000).toISOString());
    expect(parseLmst("13:16:16")).toBeCloseTo(13.271, 3);
  });

  it("refuse des seuils incohérents", () => {
    expect(validateSettings(settings)).toEqual({});
    const bad = validateSettings({ ...settings, penalty_slope_deg: 25, min_reserve_pct: -1 });
    expect(Object.keys(bad).sort()).toEqual(["min_reserve_pct", "penalty_slope_deg"]);
  });
});

describe("messages du WebSocket", () => {
  it("range chaque type de message à sa place", () => {
    const qc = new QueryClient();
    const key = queryKeys.alerts("eva-demo");
    qc.setQueryData(key, [{ ...alerts[1]! }]);
    applyMessage(wsAlert as WsMessage, qc, "eva-demo", "fictif");
    expect(qc.getQueryData<Alert[]>(key)!.map((a) => a.id)).toEqual(["alert-1", "alert-2"]);
    applyMessage(wsAlertCleared as WsMessage, qc, "eva-demo", "fictif");
    expect(qc.getQueryData<Alert[]>(key)!.map((a) => a.id)).toEqual(["alert-1"]);
    applyMessage(wsConditions as WsMessage, qc, "eva-demo", "fictif");
    expect(qc.getQueryData(queryKeys.conditionsCurrent("fictif"))).toEqual(wsConditions.payload);
    applyMessage(wsTelemetry as WsMessage, qc, "eva-demo", "fictif");
    applyMessage(wsBudget as WsMessage, qc, "eva-demo", "fictif");
    const st = useSafety.getState();
    expect(st.telemetry?.value.consumables.oxygen_pct).toBe(82);
    expect(st.budget?.value.time_to_pnr_s).toBe(5400);
    expect(st.anchor).toMatchObject({ sol: 14, utc: wsBudget.utc });
  });
});

// --- Critères d'acceptation ---------------------------------------------------------
describe("bandeau d'alertes", () => {
  it("affiche une alerte danger reçue par WebSocket en moins de 1 s et l'acquitte en une action", async () => {
    useShared.setState({ evaId: "eva-demo" });
    wrap(<AlertBanner />);
    await screen.findByText(/Aucune alerte active/);
    const socket = FakeSocket.instances.at(-1)!;
    expect(socket.url).toMatch(/\/ws\/eva\/eva-demo$/);
    act(() => socket.open());

    const t0 = performance.now();
    act(() => socket.emit(wsAlert));
    const row = await screen.findByRole("alert");
    const elapsed = performance.now() - t0;
    expect(elapsed).toBeLessThan(1000);

    // La couleur n'est jamais le seul indice : icône, niveau en texte, cause et action.
    expect(row.getAttribute("data-level")).toBe("danger");
    expect(row.textContent).toContain("⛔");
    expect(row.textContent).toContain("Danger");
    expect(row.textContent).toContain(wsAlert.payload.title);
    expect(row.textContent).toContain("Retour à l'abri");
    expect(row.textContent).toMatch(/Sol 14 · 13:16:16 LMST · 10:00:00 UTC/);

    // Une seule action pour l'acquitter.
    fireEvent.click(within(row).getByRole("button", { name: /Acquitter/ }));
    await waitFor(() =>
      expect(document.querySelector('[data-alert-id="alert-1"]')!.getAttribute("data-acknowledged")).toBe("true"),
    );
    expect(postSpy).toHaveBeenCalledWith("/api/alerts/{alert_id}/ack", { params: { path: { alert_id: "alert-1" } } });
    expect(screen.getByText(/Acquittée/)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("classe les alertes de l'API et retire celles qui sont levées", async () => {
    getData["/api/alerts"] = [alerts[1], alerts[0]];
    useShared.setState({ evaId: "eva-demo" });
    wrap(<AlertBanner />);
    await screen.findByRole("alert");
    const rows = document.querySelectorAll("[data-alert-id]");
    expect([...rows].map((r) => r.getAttribute("data-level"))).toEqual(["danger", "caution"]);
    const socket = FakeSocket.instances.at(-1)!;
    act(() => socket.emit(wsAlertCleared));
    await waitFor(() => expect(document.querySelectorAll("[data-alert-id]")).toHaveLength(1));
  });

  it("se reconnecte après une coupure", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    useShared.setState({ evaId: "eva-demo" });
    wrap(<AlertBanner />);
    const first = FakeSocket.instances.at(-1)!;
    act(() => first.open());
    expect(useSafety.getState().status).toBe("open");
    act(() => first.onclose?.());
    expect(useSafety.getState().status).toBe("closed");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    expect(FakeSocket.instances.length).toBeGreaterThan(1);
  });
});

describe("panneau sécurité", () => {
  it("montre jauges et comptes à rebours de la sortie en cours", async () => {
    useShared.setState({ evaId: "eva-demo" });
    wrap(<SafetyPanel />);
    act(() => {
      useSafety.getState().setTelemetry(wsTelemetry.payload as never);
      useSafety.getState().setBudget({ ...wsBudget.payload, reserve_pct: 35, time_to_pnr_s: 600 } as never);
    });
    await screen.findByText("Sol 14");
    const gauge = (name: string) => document.querySelector(`[data-gauge="${name}"]`)!;
    expect(gauge("Oxygène").textContent).toContain("82 %");
    expect(gauge("Oxygène").getAttribute("data-level")).toBe("ok");
    expect(gauge("Batterie").textContent).toContain("85 %");
    expect(gauge("Dose reçue").textContent).toContain("4,2 µSv");
    // Réserve 35 % < 30 + 10 : attention, en texte et en icône.
    await waitFor(() => expect(gauge("Réserve au retour").getAttribute("data-level")).toBe("caution"));
    expect(gauge("Réserve au retour").textContent).toContain("▲");
    expect(gauge("Réserve au retour").textContent).toContain("Attention");
    const pnr = document.querySelector('[data-countdown="Point de non-retour"]')!;
    expect(pnr.textContent).toMatch(/(10 min 00 s|9 min 5\d s)/);
    expect(pnr.getAttribute("data-level")).toBe("caution");
    const sunset = document.querySelector('[data-countdown="Coucher du Soleil"]')!;
    expect(sunset.textContent).toMatch(/4 h \d\d min/);
    expect(screen.getByText(/13:16:1\d LMST/)).toBeTruthy();
  });

  it("sans sortie, affiche les valeurs prévues par le plan et démarre une sortie simulée", async () => {
    useShared.setState({ activePlanId: "plan-demo", activeRouteId: "route-safest" });
    wrap(<SafetyPanel />);
    const gauge = () => document.querySelector('[data-gauge="Réserve au retour"]')!;
    await waitFor(() => expect(gauge().textContent).toContain("89 %"));
    expect(gauge().textContent).toContain("prévue par le plan");
    const start = screen.getByRole("button", { name: /Démarrer la sortie simulée/ });
    fireEvent.click(start);
    await waitFor(() => expect(useShared.getState().evaId).toBe("eva-demo"));
    expect(postSpy).toHaveBeenCalledWith("/api/eva", {
      body: { plan_id: "plan-demo", route_id: "route-safest", crew: ["EV1"] },
    });
    expect(postSpy).toHaveBeenCalledWith("/api/eva/{eva_id}/simulate", {
      params: { path: { eva_id: "eva-demo" } },
      body: { speed: 10, scenario_id: null },
    });
  });
});

describe("météo et météo spatiale", () => {
  it("affiche les conditions et signale une tempête en texte et en icône", async () => {
    getData["/api/sites/{site_id}/conditions/current"] = {
      ...conditionsExample,
      dose_rate_usv_h: 250,
      space_weather: { level: "storm", event: "SEP", source: "RAD" },
    };
    wrap(<ConditionsPanel />);
    const sw = await screen.findByText("Tempête de particules");
    expect(sw.closest("[data-space-weather]")!.textContent).toContain("⛔");
    const rate = document.querySelector('[data-row="Débit de dose"]')!;
    expect(rate.textContent).toContain("250,0 µSv/h");
    expect(rate.textContent).toContain("Danger");
    expect(document.querySelector('[data-row="Opacité (τ)"]')!.textContent).toContain("Normal");
    expect(await screen.findByText(/Prévisions \(\d+ h\)/)).toBeTruthy();
  });

  it("lance un scénario", async () => {
    wrap(<ConditionsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /Lancer/ }));
    await waitFor(() =>
      expect(postSpy).toHaveBeenCalledWith("/api/scenarios/{scenario_id}/start", {
        params: { path: { scenario_id: "solar-event" }, query: { speed: 10 } },
      }),
    );
    expect(await screen.findByRole("button", { name: /Arrêter/ })).toBeTruthy();
  });
});

describe("réglage des seuils", () => {
  it("bloque une saisie incohérente puis enregistre", async () => {
    wrap(<ThresholdsPanel />);
    const input = (await screen.findByRole("spinbutton", { name: /Pente pénalisée/ })) as HTMLInputElement;
    const save = screen.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(input, { target: { value: "25" } });
    expect(screen.getByText(/sous la pente interdite/)).toBeTruthy();
    expect(save.disabled).toBe(true);
    fireEvent.change(input, { target: { value: "12" } });
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    await waitFor(() => expect(putSpy).toHaveBeenCalled());
    expect(putSpy.mock.calls[0]![1].body).toMatchObject({ penalty_slope_deg: 12, max_slope_deg: 20 });
    expect(await screen.findByText("✓ Enregistré")).toBeTruthy();
  });
});

describe("fonctionnalité", () => {
  it("place le bandeau en haut et trois panneaux à droite", () => {
    expect(feature.id).toBe("safety");
    expect(feature.panels.map((p) => p.slot)).toEqual(["top-banner", "right", "right", "right"]);
  });
});
