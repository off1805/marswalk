/**
 * Données du profil : le plan actif et les cibles, lus par les clés partagées de
 * TanStack Query (shared/queryKeys.ts) pour partager le cache avec F2 et F6.
 */
import { useQuery } from "@tanstack/react-query";
import { api, type Plan, type Target } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { selectProfileRoute, type ProfileRouteChoice } from "./profileData";

export async function fetchPlan(planId: string): Promise<Plan> {
  const { data, error } = await api.GET("/api/plans/{plan_id}", {
    params: { path: { plan_id: planId } },
  });
  if (error || !data) throw new Error("Plan indisponible");
  return data as Plan;
}

export function usePlan(planId: string | null) {
  return useQuery({
    queryKey: queryKeys.plan(planId ?? ""),
    queryFn: () => fetchPlan(planId!),
    enabled: Boolean(planId),
    staleTime: 10_000,
  });
}

/** Noms des cibles par identifiant, pour les marqueurs et les tronçons. */
export function useTargetNames(siteId: string): Record<string, string> {
  const { data } = useQuery({
    queryKey: queryKeys.targets(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/targets", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Cibles indisponibles");
      return data as Target[];
    },
    staleTime: 10_000,
  });
  const names: Record<string, string> = {};
  for (const t of data ?? []) names[t.id] = t.name;
  return names;
}

export interface ProfileData {
  plan: Plan | undefined;
  choice: ProfileRouteChoice | null;
  targetNames: Record<string, string>;
  isLoading: boolean;
  isError: boolean;
}

export function useProfileRoute(): ProfileData {
  const siteId = useShared((s) => s.siteId);
  const activePlanId = useShared((s) => s.activePlanId);
  const activeRouteId = useShared((s) => s.activeRouteId);
  const plan = usePlan(activePlanId);
  const targetNames = useTargetNames(siteId);
  return {
    plan: plan.data,
    choice: selectProfileRoute(plan.data, activeRouteId),
    targetNames,
    isLoading: plan.isLoading,
    isError: plan.isError,
  };
}
