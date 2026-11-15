/**
 * Faux serveur (MSW) : chaque route de l'API renvoie son exemple de contracts/examples/.
 * Lancé par `pnpm dev:mock` ; les tuiles du site fictif sont servies par Vite.
 */
import { http, HttpResponse, ws } from "msw";
import alerts from "@contracts/examples/alerts.json";
import conditionsCurrent from "@contracts/examples/conditions_current.json";
import conditionsForecast from "@contracts/examples/conditions_forecast.json";
import eva from "@contracts/examples/eva.json";
import exportPlan from "@contracts/examples/export_plan.json";
import groundImages from "@contracts/examples/ground_images.json";
import hazards from "@contracts/examples/hazards.json";
import health from "@contracts/examples/health.json";
import logbook from "@contracts/examples/logbook.json";
import observation from "@contracts/examples/observation.json";
import obstacleResponse from "@contracts/examples/obstacle_response.json";
import plan from "@contracts/examples/plan.json";
import query from "@contracts/examples/query.json";
import scenarioState from "@contracts/examples/scenario_state.json";
import scenarios from "@contracts/examples/scenarios.json";
import settings from "@contracts/examples/settings.json";
import simulationState from "@contracts/examples/simulation_state.json";
import siteManifest from "@contracts/examples/site_manifest.json";
import sites from "@contracts/examples/sites.json";
import target from "@contracts/examples/target.json";
import targets from "@contracts/examples/targets.json";
import time from "@contracts/examples/time.json";
import wsAlert from "@contracts/examples/ws_alert.json";
import wsAlertCleared from "@contracts/examples/ws_alert_cleared.json";
import wsBudget from "@contracts/examples/ws_budget.json";
import wsConditions from "@contracts/examples/ws_conditions.json";
import wsRouteUpdated from "@contracts/examples/ws_route_updated.json";
import wsTelemetry from "@contracts/examples/ws_telemetry.json";

const json = (body: unknown, status = 200) => HttpResponse.json(body as object, { status });

/** Préréglages d'affichage (copie de config/presets.yaml pour le mode mock). */
export const mockPresets = [
  {
    id: "safety",
    title: "Safety",
    layers: {
      hillshade: { visible: true, opacity: 1 },
      slope: { visible: true, opacity: 0.6 },
      scarps: { visible: true, opacity: 0.8 },
      obstacles: { visible: true, opacity: 0.8 },
      radio_coverage: { visible: false, opacity: 0.5 },
      rover_traverse: { visible: true, opacity: 0.8 },
      ground_images: { visible: true, opacity: 1 },
    },
  },
  {
    id: "science",
    title: "Science",
    layers: {
      hirise_vis: { visible: true, opacity: 1 },
      crism_minerals: { visible: true, opacity: 0.6 },
      thermal_inertia: { visible: false, opacity: 0.6 },
      rover_traverse: { visible: true, opacity: 1 },
      ground_images: { visible: true, opacity: 1 },
    },
  },
  {
    id: "navigation",
    title: "Navigation",
    layers: {
      hirise_vis: { visible: true, opacity: 1 },
      hillshade: { visible: false, opacity: 0.5 },
      rover_traverse: { visible: true, opacity: 1 },
      radio_coverage: { visible: false, opacity: 0.4 },
      ground_images: { visible: true, opacity: 1 },
    },
  },
];

export const WS_SEQUENCE = [wsTelemetry, wsAlert, wsAlertCleared, wsConditions, wsRouteUpdated, wsBudget];

const evaSocket = ws.link(/\/ws\/eva\/[^/]+$/);

export const handlers = [
  http.get("/api/health", () => json(health)),
  http.get("/api/time", () => json(time)),
  http.get("/api/sites", () => json(sites)),
  http.get("/api/presets", () => json(mockPresets)),
  http.get("/api/sites/:siteId/query", () => json(query)),
  http.get("/api/sites/:siteId/hazards", () => json(hazards)),
  http.get("/api/sites/:siteId/settings", () => json(settings)),
  http.put("/api/sites/:siteId/settings", async ({ request }) => json(await request.json())),
  http.get("/api/sites/:siteId/targets", () => json(targets)),
  http.post("/api/sites/:siteId/targets", () => json(target, 201)),
  http.patch("/api/targets/:id", () => json(target)),
  http.delete("/api/targets/:id", () => new HttpResponse(null, { status: 204 })),
  http.post("/api/sites/:siteId/plans", () => json(plan, 201)),
  http.get("/api/plans/:id/export.geojson", () => json(exportPlan)),
  http.get("/api/plans/:id", () => json(plan)),
  http.patch("/api/plans/:id", () => json(plan)),
  http.get("/api/sites/:siteId/conditions/current", () => json(conditionsCurrent)),
  http.get("/api/sites/:siteId/conditions/forecast", () => json(conditionsForecast)),
  http.get("/api/scenarios", () => json(scenarios)),
  http.post("/api/scenarios/:id/start", () => json(scenarioState)),
  http.post("/api/scenarios/:id/stop", () => json({ ...scenarioState, running: false })),
  http.get("/api/alerts", () => json(alerts)),
  http.post("/api/alerts/:id/ack", () => json({ ...alerts[0], acknowledged: true })),
  http.post("/api/eva", () => json(eva, 201)),
  http.get("/api/eva/:id/logbook", () => json(logbook)),
  http.get("/api/eva/:id", () => json(eva)),
  http.post("/api/eva/:id/position", () => json(eva)),
  http.post("/api/eva/:id/observations", () => json(observation, 201)),
  http.post("/api/eva/:id/obstacles", () => json(obstacleResponse)),
  http.post("/api/eva/:id/simulate", () => json(simulationState)),
  http.get("/api/sites/:siteId/ground-images", () => json(groundImages)),
  http.get("/api/sites/:siteId/vector/:layerId", async ({ params }) => {
    const res = await fetch(`/__fixtures/sites/${params.siteId}/vector/${params.layerId}.geojson`);
    return res.ok ? json(await res.json()) : json({ detail: "Couche inconnue" }, 404);
  }),
  http.get("/api/sites/:siteId", ({ params }) =>
    params.siteId === siteManifest.site_id ? json(siteManifest) : json({ detail: "Site inconnu" }, 404),
  ),
  evaSocket.addEventListener("connection", ({ client }) => {
    for (const message of WS_SEQUENCE) client.send(JSON.stringify(message));
  }),
];
