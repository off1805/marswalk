/**
 * Recalcul automatique du plan après chaque modification des cibles.
 *
 * Règle : debounce de 400 ms, « la dernière demande gagne » via compteur de séquence.
 * Affiche un indicateur de calcul pendant le recalcul.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Target, type Plan } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";

function sameTargets(planIds: string[], targets: Target[]): boolean {
  if (planIds.length !== targets.length) return false;
  const ids = new Set(targets.map((t) => t.id));
  return planIds.every((id) => ids.has(id));
}

export function useAutoPlan(targets: Target[] | undefined) {
  const siteId = useShared((s) => s.siteId);
  const setActivePlan = useShared((s) => s.setActivePlan);
  const setActiveRoute = useShared((s) => s.setActiveRoute);
  const qc = useQueryClient();

  const [computing, setComputing] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Counter to implement "last request wins"
  const reqCounterRef = useRef(0);

  const compute = useCallback(
    async (tgts: Target[]) => {
      if (tgts.length === 0) {
        setActivePlan(null);
        setActiveRoute(null);
        return;
      }

      // Le plan actif (restauré après un rechargement, ou déjà calculé) couvre-t-il
      // exactement ces cibles ? Alors on le garde : le recalculer créerait un nouveau plan
      // et effacerait la variante choisie.
      const { activePlanId } = useShared.getState();
      if (activePlanId) {
        let current = qc.getQueryData<Plan>(queryKeys.plan(activePlanId));
        if (!current) {
          const { data } = await api.GET("/api/plans/{plan_id}", {
            params: { path: { plan_id: activePlanId } },
          });
          current = data as Plan | undefined;
          if (current) qc.setQueryData(queryKeys.plan(current.id), current);
        }
        // L'API présélectionne une variante à la création : ce n'est pas un choix de
        // l'astronaute, on ne l'applique donc pas ici (PlanSync restaure son vrai choix).
        if (current && sameTargets(current.target_ids, tgts)) return;
      }

      // Cancel previous in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Assign a sequence number to this request
      const mySeq = ++reqCounterRef.current;

      setComputing(true);
      try {
        const { data, error } = await api.POST("/api/sites/{site_id}/plans", {
          params: { path: { site_id: siteId } },
          body: {
            target_ids: tgts.map((t) => t.id),
            optimize_order: true,
            variants: ["safest", "fastest", "science"],
          },
        });

        // Ignore if a newer request has already been issued
        if (mySeq !== reqCounterRef.current) return;
        if (error || !data) return;

        const plan = data as Plan;
        qc.setQueryData(queryKeys.plan(plan.id), plan);
        setActivePlan(plan.id);
        // Don't auto-select a route — the astronaut keeps control
        if (!plan.selected_route_id) {
          setActiveRoute(null); // force user to pick
        }
      } catch (e) {
        if ((e as { name?: string }).name === "AbortError") return;
      } finally {
        if (mySeq === reqCounterRef.current) setComputing(false);
      }
    },
    [siteId, qc, setActivePlan, setActiveRoute],
  );

  useEffect(() => {
    if (!targets) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void compute(targets), 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [targets, compute]);

  return { computing };
}
