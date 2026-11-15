/**
 * Keeps the active plan and chosen route across reloads, per site.
 *
 * The shared store (frozen contract) lives in memory only: reloading the page, or
 * opening the 3D view directly, used to lose the route the user had chosen. This shell
 * component writes the plan and route ids to local storage and restores them when the
 * site is known. A plan the API no longer has (after a restart) is forgotten.
 */
import { useEffect } from "react";
import { api } from "@/shared/api/client";
import { useShared } from "@/shared/store";

const key = (siteId: string) => `marswalk.plan.${siteId}`;

interface Saved {
  planId: string;
  routeId: string | null;
}

function read(siteId: string): Saved | null {
  try {
    const raw = window.localStorage.getItem(key(siteId));
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}

function write(siteId: string, saved: Saved | null) {
  try {
    if (saved) window.localStorage.setItem(key(siteId), JSON.stringify(saved));
    else window.localStorage.removeItem(key(siteId));
  } catch {
    /* storage unavailable: the choice lasts for the session */
  }
}

export function PlanSync() {
  const siteId = useShared((s) => s.siteId);

  // Restore when the site is known.
  useEffect(() => {
    const saved = read(siteId);
    if (!saved) return;
    let cancelled = false;
    void (async () => {
      const { data, error } = await api.GET("/api/plans/{plan_id}", {
        params: { path: { plan_id: saved.planId } },
      });
      if (cancelled) return;
      const state = useShared.getState();
      if (state.siteId !== siteId || state.activePlanId) return;
      if (error || !data || data.site_id !== siteId) {
        write(siteId, null);
        return;
      }
      const routeId = saved.routeId ?? data.selected_route_id ?? null;
      state.setActivePlan(data.id);
      if (routeId && data.routes.some((r) => r.id === routeId)) state.setActiveRoute(routeId);
    })();
    return () => {
      cancelled = true;
    };
  }, [siteId]);

  // Save every change.
  useEffect(
    () =>
      useShared.subscribe((s, prev) => {
        if (s.activePlanId === prev.activePlanId && s.activeRouteId === prev.activeRouteId) return;
        if (s.siteId !== prev.siteId) return;
        write(s.siteId, s.activePlanId ? { planId: s.activePlanId, routeId: s.activeRouteId } : null);
      }),
    [],
  );

  return null;
}
