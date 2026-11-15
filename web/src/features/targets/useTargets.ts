/**
 * Hooks TanStack Query pour les cibles et le plan actif.
 * Toute communication avec le serveur passe ici ; les composants n'appellent jamais
 * directement le client API.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { api, type Target, type Schemas } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";

type TargetCreate = Schemas["TargetCreate"];
type TargetUpdate = Schemas["TargetUpdate"];

// ── Lecture ──────────────────────────────────────────────────────────────────

export function useTargets() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.targets(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/targets", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error("Cibles indisponibles");
      return data as Target[];
    },
    staleTime: 30_000,
  });
}

export function usePlan(planId: string | null) {
  return useQuery({
    queryKey: queryKeys.plan(planId ?? ""),
    queryFn: async () => {
      if (!planId) return null;
      const { data, error } = await api.GET("/api/plans/{plan_id}", {
        params: { path: { plan_id: planId } },
      });
      if (error || !data) throw new Error("Plan indisponible");
      return data;
    },
    enabled: Boolean(planId),
    staleTime: 10_000,
  });
}

export function useHazards() {
  const siteId = useShared((s) => s.siteId);
  const preset = useShared((s) => s.preset);
  return useQuery({
    queryKey: queryKeys.hazards(siteId, preset),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}/hazards", {
        params: { path: { site_id: siteId }, query: { preset } },
      });
      if (error || !data) throw new Error("Zones de risque indisponibles");
      return data;
    },
    staleTime: 60_000,
  });
}

// ── Mutations ─────────────────────────────────────────────────────────────────

function invalidateTargets(qc: QueryClient, siteId: string) {
  void qc.invalidateQueries({ queryKey: queryKeys.targets(siteId) });
}

export function useCreateTarget() {
  const qc = useQueryClient();
  const siteId = useShared((s) => s.siteId);
  return useMutation({
    mutationFn: async (body: TargetCreate) => {
      const { data, error } = await api.POST("/api/sites/{site_id}/targets", {
        params: { path: { site_id: siteId } },
        body,
      });
      if (error || !data) throw new Error("Échec de la création de la cible");
      return data as Target;
    },
    onSuccess: () => invalidateTargets(qc, siteId),
  });
}

export function useUpdateTarget() {
  const qc = useQueryClient();
  const siteId = useShared((s) => s.siteId);
  return useMutation({
    mutationFn: async ({
      id,
      ...patch
    }: TargetUpdate & { id: string }) => {
      const { data, error } = await api.PATCH("/api/targets/{target_id}", {
        params: { path: { target_id: id } },
        body: patch,
      });
      if (error || !data) throw new Error("Échec de la mise à jour de la cible");
      return data as Target;
    },
    onSuccess: () => invalidateTargets(qc, siteId),
  });
}

export function useDeleteTarget() {
  const qc = useQueryClient();
  const siteId = useShared((s) => s.siteId);
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE("/api/targets/{target_id}", {
        params: { path: { target_id: id } },
      });
      if (error) throw new Error("Échec de la suppression de la cible");
    },
    onSuccess: () => invalidateTargets(qc, siteId),
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  const siteId = useShared((s) => s.siteId);
  return useMutation({
    mutationFn: async (targetIds: string[]) => {
      const { data, error } = await api.POST("/api/sites/{site_id}/plans", {
        params: { path: { site_id: siteId } },
        body: {
          target_ids: targetIds,
          optimize_order: true,
          variants: ["safest", "fastest", "science"],
        },
      });
      if (error || !data) throw new Error("Échec du calcul du plan");
      return data;
    },
    onSuccess: (plan) => {
      qc.setQueryData(queryKeys.plan(plan.id), plan);
    },
  });
}

export function useSelectRoute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      planId,
      routeId,
    }: {
      planId: string;
      routeId: string;
    }) => {
      const { data, error } = await api.PATCH("/api/plans/{plan_id}", {
        params: { path: { plan_id: planId } },
        body: { selected_route_id: routeId },
      });
      if (error || !data) throw new Error("Échec de la sélection de variante");
      return data;
    },
    onSuccess: (plan) => {
      qc.setQueryData(queryKeys.plan(plan.id), plan);
    },
  });
}
