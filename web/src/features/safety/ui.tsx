/** Petits éléments d'affichage de F4 : niveau, jauge, compte à rebours, horloge locale. */
import { useEffect, useState } from "react";
import { alertLevels, colors, textColors } from "@/shared/theme";
import type { GaugeLevel } from "./thresholds";

/** Couleur, icône et libellé d'un niveau ; « ok » n'est pas un niveau d'alerte. */
export const levelMeta: Record<GaugeLevel, { color: string; ink: string; icon: string; label: string }> = {
  ok: { color: colors.ok, ink: "#000000", icon: "✓", label: "Normal" },
  ...alertLevels,
};

/** Re-rendu périodique, pour les comptes à rebours et l'horloge. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** Niveau en icône et texte, jamais la couleur seule (ENF-06). */
export function LevelTag({ level }: { level: GaugeLevel }) {
  const meta = levelMeta[level];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-bold" style={{ color: textColors[level] }}>
      <span aria-hidden="true">{meta.icon}</span>
      {meta.label}
    </span>
  );
}

export function Gauge({
  label,
  value,
  pct,
  level,
  hint,
}: {
  label: string;
  /** Valeur affichée, déjà mise en forme. */
  value: string;
  /** Remplissage de la barre, 0 à 100 ; aucune barre si absent. */
  pct?: number | null;
  level: GaugeLevel;
  hint?: string;
}) {
  const meta = levelMeta[level];
  const fill = pct == null ? null : Math.max(0, Math.min(100, pct));
  return (
    <div data-gauge={label} data-level={level} className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm">{label}</span>
        <span className="flex items-baseline gap-2">
          <strong className="tabular-nums">{value}</strong>
          <LevelTag level={level} />
        </span>
      </div>
      {fill != null && (
        <div
          role="meter"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(fill)}
          aria-valuetext={`${value}, ${meta.label}`}
          className="h-2 overflow-hidden rounded bg-[var(--surface-2)]"
        >
          <div className="h-full" style={{ width: `${fill}%`, background: meta.color }} />
        </div>
      )}
      {hint && <span className="text-xs text-[var(--text-muted)]">{hint}</span>}
    </div>
  );
}

export function Countdown({ label, value, level, hint }: { label: string; value: string; level: GaugeLevel; hint?: string }) {
  const meta = levelMeta[level];
  return (
    <div
      data-countdown={label}
      data-level={level}
      className="flex flex-col rounded-md border-l-4 bg-[var(--surface-2)] px-2 py-1"
      style={{ borderColor: meta.color }}
    >
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <strong className="text-lg tabular-nums" aria-live="off">
        {value}
      </strong>
      <LevelTag level={level} />
      {hint && <span className="text-xs text-[var(--text-muted)]">{hint}</span>}
    </div>
  );
}
