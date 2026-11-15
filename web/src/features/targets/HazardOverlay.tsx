/**
 * Légende des zones interdites/pénalisées et tooltip de survol.
 * Règle ENF-06 : couleur + icône + texte pour chaque type de zone.
 */
import { useShared } from "@/shared/store";
import { useHazards } from "./useTargets";

export function HazardLegend() {
  return (
    <div
      className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-xs"
      aria-label="Hazard zone legend"
    >
      <p className="mb-1 font-semibold text-[var(--text-muted)] uppercase tracking-wide text-[10px]">
        Zones
      </p>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm flex-shrink-0"
            style={{ backgroundColor: "rgba(213,94,0,0.6)", border: "1.5px solid rgba(213,94,0,0.9)" }}
            aria-hidden="true"
          />
          <span>⛔ Forbidden</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm flex-shrink-0"
            style={{ backgroundColor: "rgba(230,159,0,0.4)", border: "1.5px solid rgba(230,159,0,0.7)" }}
            aria-hidden="true"
          />
          <span>▲ Penalized</span>
        </div>
      </div>
    </div>
  );
}

export function HazardHoverTooltip({ cause }: { cause: string | null }) {
  if (!cause) return null;
  return (
    <div
      className="pointer-events-none rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs shadow-lg"
      role="tooltip"
    >
      <span className="font-semibold">Cause:</span> {cause}
    </div>
  );
}

/** Overlay affiché sur la carte quand des zones existent. */
export function HazardsOverlay({ hazardHover }: { hazardHover: string | null }) {
  const siteId = useShared((s) => s.siteId);
  const { data: hazards } = useHazards();
  if (!hazards?.features?.length) return null;
  void siteId; // used by hook

  return (
    <div className="absolute bottom-6 left-2 flex flex-col gap-1 items-start">
      <HazardLegend />
      <HazardHoverTooltip cause={hazardHover} />
    </div>
  );
}
