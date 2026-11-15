/** Requêtes et mutations de F4, sous les clés partagées de shared/queryKeys.ts. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type Alert,
  type Conditions,
  type Eva,
  type Plan,
  type SafetySettings,
  type Schemas,
  type TimeInfo,
} from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { useSafety } from "./safetyStore";

export type Forecast = Schemas["Forecast"];
export type Scenario = Schemas["Scenario"];
export type ScenarioState = Schemas["ScenarioState"];

/** Hors WebSocket ouvert, on relit les alertes régulièrement. */
const ALERT_POLL_MS = 5_000;

export function useAlerts() {
  const evaId = useShared((s) => s.evaId);
  const live = useSafety((s) => s.status === "open");
  return useQuery({
    queryKey: queryKeys.alerts(evaId ?? undefined),
    queryFn: async (): Promise<Alert[]> => {
      const { data, error } = await api.GET("/api/alerts", {
        params: { query: { eva_id: evaId ?? undefined, active: true } },
      });
      if (error || !data) throw new Error("Alertes indisponibles");
      return data as Alert[];
    },
    refetchInterval: live ? false : ALERT_POLL_MS,
  });
}

/** Acquittement en une action, avec mise à jour optimiste du bandeau. */
export function useAcknowledge() {
  const client = useQueryClient();
  const evaId = useShared((s) => s.evaId);
  const key = queryKeys.alerts(evaId ?? undefined);
  return useMutation({
    mutationFn: async (alertId: string): Promise<Alert> => {
      const { data, error } = await api.POST("/api/alerts/{alert_id}/ack", {
        params: { path: { alert_id: alertId } },
      });
      if (error || !data) throw new Error("Acquittement refusé");
      return data as Alert;
    },
    onMutate: async (alertId) => {
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<Alert[]>(key);
      client.setQueryData<Alert[]>(key, (list) =>
        list?.map((a) =>
          a.id === alertId ? { ...a, acknowledged: true, acknowledged_at: new Date().toISOString() } : a,
        ),
      );
      return { previous };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.previous) client.setQueryData(key, ctx.previous);
    },
    onSuccess: (alert) => {
      client.setQueryData<Alert[]>(key, (list) => list?.map((a) => (a.id === alert.id ? { ...a, ...alert } : a)));
    },
  });
}

export function useConditions() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.conditionsCurrent(siteId),
    queryFn: async (): Promise<Conditions> => {
      const { data, error } = await api.GET("/api/sites/{site_id}/conditions/current", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Conditions indisponibles");
      return data;
    },
    refetchInterval: 30_000,
  });
}

export const FORECAST_HOURS = 12;

export function useForecast() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.conditionsForecast(siteId, FORECAST_HOURS),
    queryFn: async (): Promise<Forecast> => {
      const { data, error } = await api.GET("/api/sites/{site_id}/conditions/forecast", {
        params: { path: { site_id: siteId }, query: { hours: FORECAST_HOURS } },
      });
      if (error || !data) throw new Error("Prévisions indisponibles");
      return data;
    },
    refetchInterval: 5 * 60_000,
  });
}

export function useSettings() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.settings(siteId),
    queryFn: async (): Promise<SafetySettings> => {
      const { data, error } = await api.GET("/api/sites/{site_id}/settings", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Seuils indisponibles");
      return data;
    },
    staleTime: 60_000,
  });
}

/** Enregistre les seuils, puis fait relire les zones dangereuses et le plan qui en dépendent. */
export function useSaveSettings() {
  const client = useQueryClient();
  const siteId = useShared((s) => s.siteId);
  return useMutation({
    mutationFn: async (settings: SafetySettings): Promise<SafetySettings> => {
      const { data, error } = await api.PUT("/api/sites/{site_id}/settings", {
        params: { path: { site_id: siteId } },
        body: settings,
      });
      if (error || !data) throw new Error("Seuils refusés par le serveur");
      return data;
    },
    onSuccess: (saved) => {
      client.setQueryData(queryKeys.settings(siteId), saved);
      void client.invalidateQueries({ queryKey: ["sites", siteId, "hazards"] });
      void client.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

/** Horloge du site ; resserre le rafraîchissement partagé (la coquille relit toutes les 60 s). */
export function useTime() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.time(siteId),
    queryFn: async (): Promise<TimeInfo> => {
      const { data, error } = await api.GET("/api/time", { params: { query: { site_id: siteId } } });
      if (error || !data) throw new Error("Heure martienne indisponible");
      return data;
    },
    refetchInterval: 15_000,
  });
}

/** Sortie en cours ; relue régulièrement quand le WebSocket n'est pas ouvert. */
export function useEva() {
  const evaId = useShared((s) => s.evaId);
  const live = useSafety((s) => s.status === "open");
  return useQuery({
    queryKey: queryKeys.eva(evaId ?? ""),
    enabled: !!evaId,
    queryFn: async (): Promise<Eva> => {
      const { data, error } = await api.GET("/api/eva/{eva_id}", { params: { path: { eva_id: evaId! } } });
      if (error || !data) throw new Error("Sortie indisponible");
      return data as Eva;
    },
    refetchInterval: live ? 30_000 : 5_000,
  });
}

/** Plan actif, pour les valeurs prévues avant la sortie. */
export function usePlan() {
  const planId = useShared((s) => s.activePlanId);
  return useQuery({
    queryKey: queryKeys.plan(planId ?? ""),
    enabled: !!planId,
    queryFn: async (): Promise<Plan> => {
      const { data, error } = await api.GET("/api/plans/{plan_id}", { params: { path: { plan_id: planId! } } });
      if (error || !data) throw new Error("Plan indisponible");
      return data as Plan;
    },
  });
}

export function useScenarios() {
  return useQuery({
    queryKey: queryKeys.scenarios(),
    queryFn: async (): Promise<Scenario[]> => {
      const { data, error } = await api.GET("/api/scenarios");
      if (error || !data) throw new Error("Scénarios indisponibles");
      return data;
    },
    staleTime: Infinity,
  });
}

/** Démarre une sortie sur la variante active, puis lance l'astronaute virtuel. */
export function useStartEva() {
  const setEvaId = useShared((s) => s.setEvaId);
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (args: { planId: string; routeId: string; scenarioId: string | null; speed: number }) => {
      const created = await api.POST("/api/eva", {
        body: { plan_id: args.planId, route_id: args.routeId, crew: ["EV1"] },
      });
      if (created.error || !created.data) throw new Error("Démarrage de la sortie refusé");
      const eva = created.data as Eva;
      const sim = await api.POST("/api/eva/{eva_id}/simulate", {
        params: { path: { eva_id: eva.id } },
        body: { speed: args.speed, scenario_id: args.scenarioId },
      });
      if (sim.error) throw new Error("Simulation refusée");
      return eva;
    },
    onSuccess: (eva) => {
      client.setQueryData(queryKeys.eva(eva.id), eva);
      setEvaId(eva.id);
    },
  });
}

export function useScenarioControl() {
  return useMutation({
    mutationFn: async (args: { scenarioId: string; run: boolean; speed?: number }): Promise<ScenarioState> => {
      const res = args.run
        ? await api.POST("/api/scenarios/{scenario_id}/start", {
            params: { path: { scenario_id: args.scenarioId }, query: { speed: args.speed ?? 1 } },
          })
        : await api.POST("/api/scenarios/{scenario_id}/stop", {
            params: { path: { scenario_id: args.scenarioId } },
          });
      if (res.error || !res.data) throw new Error("Scénario refusé");
      return res.data;
    },
  });
}
