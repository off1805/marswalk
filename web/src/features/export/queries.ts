/** Requêtes de l'export (X1), sur les clés partagées de @/shared/queryKeys. */
import { useQuery } from "@tanstack/react-query";
import { api, type FeatureCollection, type Plan } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import type { Logbook } from "./format";

export function usePlan(planId: string | null) {
  return useQuery({
    queryKey: queryKeys.plan(planId ?? ""),
    enabled: planId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/plans/{plan_id}", {
        params: { path: { plan_id: planId! } },
      });
      if (error || !data) throw new Error(`Plan ${planId} unavailable`);
      return data as Plan;
    },
  });
}

export function usePlanGeojson(planId: string | null) {
  return useQuery({
    queryKey: [...queryKeys.plan(planId ?? ""), "export"],
    enabled: planId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/plans/{plan_id}/export.geojson", {
        params: { path: { plan_id: planId! } },
      });
      if (error || !data) throw new Error(`Plan export ${planId} unavailable`);
      return data as FeatureCollection;
    },
  });
}

export function useLogbook(evaId: string | null, refetchMs?: number) {
  return useQuery({
    queryKey: queryKeys.logbook(evaId ?? ""),
    enabled: evaId !== null,
    refetchInterval: refetchMs,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/eva/{eva_id}/logbook", {
        params: { path: { eva_id: evaId! } },
      });
      if (error || !data) throw new Error(`Logbook for ${evaId} unavailable`);
      return data as Logbook;
    },
  });
}

export function planGeojsonUrl(planId: string): string {
  return `/api/plans/${encodeURIComponent(planId)}/export.geojson`;
}
