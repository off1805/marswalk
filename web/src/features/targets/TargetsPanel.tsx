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

  const selectedTarget = targets?.find((t) => t.id === selectedTargetId);

  function toggleAddMode() {
    setPickMode(pickMode === "addTarget" ? "none" : "addTarget");
  }

  return (
    <div className="flex flex-col gap-2" aria-label="Panneau cibles et itinéraire">
      {/* En-tête cibles */}
      <Panel title="Cibles">
        {/* Bouton d'ajout */}
        <Button
          variant={pickMode === "addTarget" ? "primary" : "secondary"}
          className="mb-2 w-full"
          onClick={toggleAddMode}
          aria-pressed={pickMode === "addTarget"}
          aria-label="Ajouter une cible (cliquez sur la carte)"
        >
          {pickMode === "addTarget"
            ? "📍 Cliquez sur la carte…"
            : "+ Ajouter une cible"}
        </Button>

        {/* Indicateur de calcul */}
        {computing && (
          <div
            className="mb-2 flex items-center gap-2 rounded bg-[var(--surface-2)] px-2 py-1 text-xs text-[var(--text-info)]"
            role="status"
            aria-live="polite"
            aria-label="Calcul de l'itinéraire en cours"
          >
            <span className="inline-block animate-spin">⟳</span>
            <span>Calcul de l'itinéraire en cours…</span>
          </div>
        )}

        {/* Liste des cibles */}
        {targetsLoading ? (
          <p className="text-xs text-[var(--text-muted)] animate-pulse">
            Chargement des cibles…
          </p>
        ) : !targets || targets.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">
            Aucune cible. Cliquez sur « + Ajouter une cible » puis sur la carte.
          </p>
        ) : (
          <ul className="space-y-1" role="list" aria-label="Liste des cibles">
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
                  aria-label={`Cible ${t.name}`}
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

      {/* Fiche de la cible sélectionnée */}
      {selectedTarget && (
        <TargetCard
          target={selectedTarget}
          onClose={() => selectTarget(null)}
        />
      )}

      {/* Comparateur de variantes */}
      {plan && plan.routes.length > 0 && (
        <Panel title="Variantes d'itinéraire">
          <RouteComparator plan={plan as import("@/shared/api/client").Plan} />
        </Panel>
      )}
    </div>
  );
}
