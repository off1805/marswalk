import { alertLevels, type AlertLevel } from "../theme";

/** Niveau d'alerte : couleur, icône et texte ensemble (ENF-06). */
export function AlertBadge({ level, text }: { level: AlertLevel; text?: string }) {
  const meta = alertLevels[level];
  return (
    <span
      role="status"
      className="inline-flex items-center gap-1 rounded px-2 py-0.5 font-bold text-white"
      style={{ background: meta.color }}
    >
      <span aria-hidden="true">{meta.icon}</span>
      {text ?? meta.label}
    </span>
  );
}
