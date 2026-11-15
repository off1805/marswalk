/**
 * Panneau principal F2 — slot `right`.
 *
 * Affiche la liste des cibles, le bouton d'ajout, le comparateur de variantes
 * et l'indicateur de calcul.
 *
 * Ce composant injecte aussi le QueryClient dans le module F2 (index.ts) pour
 * que mapLayers() puisse lire le cache de façon synchrone.
 */
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Panel } from "@/shared/ui/Panel";
import { Button } from "@/shared/ui/Button";
import { useShared } from "@/shared/store";
import { useTargets, usePlan } from "./useTargets";
import { useAutoPlan } from "./useAutoPlan";
import { TargetCard } from "./TargetCard";
import { RouteComparator } from "./RouteComparator";
import { injectQueryClient } from "./index";
import { targetsStore } from "./targetsStore";

export function TargetsPanel() {
  const qc = useQueryClient();

  // Injecte le QueryClient dans le module pour que mapLayers() y ait accès
  useEffect(() => {
    injectQueryClient(qc);
  }, [qc]);

  const pickMode = useShared((s) => s.pickMode);
  const setPickMode = useShared((s) => s.setPickMode);
  const selectedTargetId = useShared((s) => s.selectedTargetId);
  const selectTarget = useShared((s) => s.selectTarget);
  const activePlanId = useShared((s) => s.activePlanId);

  const { data: targets, isLoading: targetsLoading } = useTargets();
  const { data: plan } = usePlan(activePlanId);
  const { computing } = useAutoPlan(targets);

  const actionError = targetsStore((s) => s.actionError);
  const selectedTarget = targets?.find((t) => t.id === selectedTargetId);

  function toggleAddMode() {
    setPickMode(pickMode === "addTarget" ? "none" : "addTarget");
  }

  return (
    <div className="flex flex-col gap-2" aria-label="Targets and route panel">
      {/* Targets header */}
      <Panel title="Science Targets">
        {/* Add button */}
        <Button
          variant={pickMode === "addTarget" ? "primary" : "secondary"}
          className="mb-2 w-full"
          onClick={toggleAddMode}
          aria-pressed={pickMode === "addTarget"}
          aria-label="Add a target (click on the map)"
        >
          {pickMode === "addTarget"
            ? "📍 Click on the map…"
            : "+ Add a target"}
        </Button>

        {actionError && (
          <p role="alert" className="mb-2 text-xs font-semibold text-[var(--text-danger)]">
            ▲ {actionError}
          </p>
        )}

        {/* Computing indicator */}
        {computing && (
          <div
            className="mb-2 flex items-center gap-2 rounded bg-[var(--surface-2)] px-2 py-1 text-xs text-[var(--text-info)]"
            role="status"
            aria-live="polite"
            aria-label="Route calculation in progress"
          >
            <span className="inline-block animate-spin">⟳</span>
            <span>Calculating route…</span>
          </div>
        )}

        {/* Target list */}
        {targetsLoading ? (
          <p className="text-xs text-[var(--text-muted)] animate-pulse">
            Loading targets…
          </p>
        ) : !targets || targets.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">
            No targets. Click "+ Add a target" then click on the map.
          </p>
        ) : (
          <ul className="space-y-1" role="list" aria-label="Target list">
            {targets.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className={`w-full rounded px-2 py-1.5 text-left text-xs transition-all ${
                    selectedTargetId === t.id
                      ? "bg-[var(--color-info)] text-white"
                      : "bg-[var(--surface-2)] text-[var(--text)] hover:bg-[var(--border)]"
                  }`}
                  onClick={() =>
                    selectTarget(selectedTargetId === t.id ? null : t.id)
                  }
                  aria-pressed={selectedTargetId === t.id}
                  aria-label={`Target ${t.name}`}
                >
                  <span className="font-semibold">{t.name}</span>
                  {t.priority !== undefined && (
                    <span className="ml-2 text-[10px] opacity-70">
                      P{t.priority}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Selected target card */}
      {selectedTarget && (
        <TargetCard
          target={selectedTarget}
          onClose={() => selectTarget(null)}
        />
      )}

      {/* Route variant comparator */}
      {plan && plan.routes.length > 0 && (
        <Panel title="Route Variants">
          <RouteComparator plan={plan as import("@/shared/api/client").Plan} />
        </Panel>
      )}
    </div>
  );
}
