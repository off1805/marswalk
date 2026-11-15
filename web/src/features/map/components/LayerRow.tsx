import { useState } from "react";
import { AlertBadge } from "@/shared/ui/AlertBadge";
import { LegendView } from "./LegendView";
import type { LayerControlProps } from "../types";

export function LayerRow({
  layer,
  view,
  onToggleVisibility,
  onChangeOpacity,
}: LayerControlProps) {
  const [showDetails, setShowDetails] = useState(false);
  const isDegraded = layer.status === "degraded";
  const isMissing = layer.status === "missing";

  return (
    <div
      data-testid={`layer-row-${layer.id}`}
      className={`rounded-md border border-[var(--border)] p-2 transition-colors ${
        view.visible ? "bg-[var(--surface-2)]" : "bg-[var(--surface)] opacity-85"
      }`}
    >
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id={`toggle-${layer.id}`}
          checked={view.visible}
          disabled={isMissing}
          onChange={(e) => onToggleVisibility(e.target.checked)}
          className="h-4 w-4 rounded accent-[var(--color-info)]"
        />
        <label
          htmlFor={`toggle-${layer.id}`}
          className="min-w-0 flex-1 cursor-pointer select-none text-xs font-semibold truncate text-[var(--text)]"
          title={layer.title}
        >
          {layer.title}
        </label>

        {isDegraded && (
          <AlertBadge level="caution" text="Dégradé" />
        )}
        {isMissing && (
          <span className="text-[10px] text-[var(--text-muted)] italic">Absente</span>
        )}

        <button
          type="button"
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] px-1 py-0.5"
          aria-label={`Détails de la couche ${layer.title}`}
        >
          {showDetails ? "▲" : "▼"}
        </button>
      </div>

      {view.visible && (
        <div className="mt-2 flex items-center gap-2 pl-6 text-xs text-[var(--text-muted)]">
          <label htmlFor={`opacity-${layer.id}`} className="text-[10px]">
            Opacité :
          </label>
          <input
            id={`opacity-${layer.id}`}
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={view.opacity}
            onChange={(e) => onChangeOpacity(parseFloat(e.target.value))}
            className="h-1 flex-1 accent-[var(--color-info)]"
            aria-label={`Opacité de la couche ${layer.title}`}
          />
          <span className="w-8 text-right font-mono text-[10px]">
            {Math.round(view.opacity * 100)}%
          </span>
        </div>
      )}

      {/* Légende affichée quand la couche est visible ou détaillée */}
      {view.visible && layer.legend && (
        <div className="pl-6">
          <LegendView legend={layer.legend} unit={layer.unit} />
        </div>
      )}

      {/* Métadonnées de traçabilité ENF-03 / ENF-04 */}
      {showDetails && (
        <div className="mt-2 border-t border-[var(--border)] pt-1.5 pl-6 text-[10px] text-[var(--text-muted)] space-y-0.5">
          <div>
            <span className="font-semibold">Instrument :</span> {layer.source.instrument} ({layer.source.mission})
          </div>
          {layer.resolution_m && (
            <div>
              <span className="font-semibold">Résolution :</span> {layer.resolution_m} m
            </div>
          )}
          {layer.acquired && (
            <div>
              <span className="font-semibold">Acquisition :</span> {layer.acquired}
            </div>
          )}
          {layer.uncertainty?.coreg_m !== undefined && layer.uncertainty.coreg_m !== null && (
            <div>
              <span className="font-semibold">Recalage :</span> ±{layer.uncertainty.coreg_m} m
            </div>
          )}
          {layer.status_note && (
            <div className="text-[var(--color-caution)] font-medium">
              Note : {layer.status_note}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
