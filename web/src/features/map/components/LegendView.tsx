import type { LegendViewProps } from "../types";

/**
 * Rendu d'une légende cartographique continue ou catégorielle (ENF-06).
 */
export function LegendView({ legend, unit }: LegendViewProps) {
  if (!legend || !legend.stops || legend.stops.length === 0) {
    return null;
  }

  if (legend.type === "continuous") {
    // Construction du dégradé CSS
    const sortedStops = [...legend.stops].sort((a, b) => a.value - b.value);
    const minVal = sortedStops[0]?.value ?? 0;
    const maxVal = sortedStops[sortedStops.length - 1]?.value ?? 0;
    const range = maxVal - minVal || 1;

    const gradientParts = sortedStops.map((stop) => {
      const pct = Math.round(((stop.value - minVal) / range) * 100);
      return `${stop.color} ${pct}%`;
    });
    const gradient = `linear-gradient(to right, ${gradientParts.join(", ")})`;

    return (
      <div className="mt-1 flex flex-col gap-0.5" aria-label={`Continuous legend in ${unit ?? ""}`}>
        <div
          className="h-2.5 w-full rounded border border-[var(--border)]"
          style={{ background: gradient }}
        />
        <div className="flex justify-between text-[10px] text-[var(--text-muted)] font-mono">
          <span>{minVal}{unit ? ` ${unit}` : ""}</span>
          <span>{maxVal}{unit ? ` ${unit}` : ""}</span>
        </div>
      </div>
    );
  }

  // Légende catégorielle
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Class legend">
      {legend.stops.map((stop, idx) => (
        <span
          key={`${stop.value}-${idx}`}
          className="inline-flex items-center gap-1 rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px]"
        >
          <span
            className="inline-block h-2.5 w-2.5 rounded-full border border-black/20"
            style={{ backgroundColor: stop.color }}
            aria-hidden="true"
          />
          <span className="text-[var(--text)]">{stop.label ?? stop.value}</span>
        </span>
      ))}
    </div>
  );
}
