/**
 * Bandeau d'alertes (top-banner) : hiérarchisé, une action pour acquitter (EF-08, ENF-08).
 * Il porte aussi la connexion WebSocket, puisqu'il est toujours affiché sur la carte.
 */
import { useState } from "react";
import type { Alert } from "@/shared/api/client";
import { Button } from "@/shared/ui";
import { useAcknowledge, useAlerts } from "./queries";
import { formatNumber, formatUtc, sortAlerts } from "./thresholds";
import { levelMeta } from "./ui";
import { useSafetyStream } from "./useSafetyStream";

/** Nombre d'alertes affichées sans déplier. */
const VISIBLE = 3;

function unitLabel(unit: string | null | undefined): string {
  if (!unit) return "";
  return unit === "deg" ? "°" : ` ${unit}`;
}

function AlertRow({ alert, onAck, pending }: { alert: Alert; onAck: (id: string) => void; pending: boolean }) {
  const meta = levelMeta[alert.level];
  const urgent = alert.level === "danger" && !alert.acknowledged;
  const measured =
    alert.value != null
      ? `${formatNumber(alert.value, 1)}${unitLabel(alert.unit)}` +
        (alert.threshold != null ? ` (seuil ${formatNumber(alert.threshold, 1)}${unitLabel(alert.unit)})` : "")
      : null;
  return (
    <li
      role={urgent ? "alert" : undefined}
      data-alert-id={alert.id}
      data-level={alert.level}
      data-acknowledged={alert.acknowledged ? "true" : "false"}
      className={`flex flex-wrap items-center gap-x-4 gap-y-1 border-l-8 bg-[var(--surface)] px-3 py-2 ${
        alert.acknowledged ? "opacity-70" : ""
      }`}
      style={{ borderColor: meta.color }}
    >
      <span
        className="inline-flex items-center gap-1 rounded px-2 py-0.5 font-bold text-white"
        style={{ background: meta.color }}
      >
        <span aria-hidden="true">{meta.icon}</span>
        {meta.label}
      </span>
      <span className="min-w-0 flex-1">
        <strong className={urgent ? "text-lg" : ""}>{alert.title}</strong>
        <span className="ml-2">{alert.message}</span>
        {measured && <span className="ml-2 text-sm text-[var(--text-muted)]">{measured}</span>}
      </span>
      <span className="font-bold">
        <span aria-hidden="true">➜ </span>
        {alert.action}
      </span>
      <span className="text-xs tabular-nums text-[var(--text-muted)]">
        Sol {alert.sol} · {alert.lmst} LMST · {formatUtc(alert.utc)}
      </span>
      {alert.acknowledged ? (
        <span className="text-sm font-semibold">✓ Acquittée</span>
      ) : (
        <Button
          variant={alert.level === "danger" ? "danger" : "secondary"}
          onClick={() => onAck(alert.id)}
          disabled={pending}
          aria-label={`Acquitter : ${alert.title}`}
        >
          Acquitter
        </Button>
      )}
    </li>
  );
}

export function AlertBanner() {
  useSafetyStream();
  const alerts = useAlerts();
  const ack = useAcknowledge();
  const [expanded, setExpanded] = useState(false);
  const sorted = sortAlerts(alerts.data ?? []);
  const shown = expanded ? sorted : sorted.slice(0, VISIBLE);
  const hidden = sorted.length - shown.length;

  return (
    <section aria-label="Alertes" className="border-b border-[var(--border)] bg-[var(--surface-2)]">
      {sorted.length === 0 ? (
        <p className="px-4 py-1 text-sm" role="status">
          {alerts.isError ? "○ Alertes indisponibles" : "✓ Aucune alerte active"}
        </p>
      ) : (
        <ul className="flex flex-col gap-px">
          {shown.map((a) => (
            <AlertRow key={a.id} alert={a} onAck={(id) => ack.mutate(id)} pending={ack.isPending && ack.variables === a.id} />
          ))}
        </ul>
      )}
      {(hidden > 0 || expanded) && sorted.length > VISIBLE && (
        <button type="button" className="px-4 py-1 text-sm underline" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Réduire" : `+ ${hidden} autre${hidden > 1 ? "s" : ""} alerte${hidden > 1 ? "s" : ""}`}
        </button>
      )}
    </section>
  );
}
