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
        (alert.threshold != null ? ` (threshold ${formatNumber(alert.threshold, 1)}${unitLabel(alert.unit)})` : "")
      : null;
  return (
    <li
      role={urgent ? "alert" : undefined}
      data-alert-id={alert.id}
      data-level={alert.level}
      data-acknowledged={alert.acknowledged ? "true" : "false"}
      className={`pane flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 text-sm ${alert.acknowledged ? "opacity-70" : ""}`}
      style={{ borderColor: alert.acknowledged ? undefined : meta.color }}
    >
      <span
        className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wider"
        style={{ background: meta.color, color: meta.ink }}
      >
        <span aria-hidden="true">{meta.icon}</span>
        {meta.label}
      </span>
      <span className="min-w-[14rem] flex-1">
        <span className="block">
          <strong className={urgent ? "font-semibold" : "font-medium"}>{alert.title}</strong>
          <span className="ml-2 text-[var(--text-muted)]">{alert.message}</span>
        </span>
        <span className="mt-0.5 flex flex-wrap items-baseline gap-x-3 text-xs">
          <span className="font-semibold">
            <span aria-hidden="true">→ </span>
            {alert.action}
          </span>
          {measured && <span className="font-mono tabular-nums text-[var(--text-muted)]">{measured}</span>}
          <span className="font-mono text-[11px] tabular-nums text-[var(--text-faint)]">
            Sol {alert.sol} · {alert.lmst} LMST · {formatUtc(alert.utc)}
          </span>
        </span>
      </span>
      {alert.acknowledged ? (
        <span className="shrink-0 text-xs font-semibold">✓ Acknowledged</span>
      ) : (
        <Button
          variant={alert.level === "danger" ? "danger" : "secondary"}
          onClick={() => onAck(alert.id)}
          disabled={pending}
          aria-label={`Acknowledge: ${alert.title}`}
          className="shrink-0"
        >
          Acknowledge
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
    <section aria-label="Alerts" className="flex flex-col items-center gap-1.5">
      {sorted.length === 0 ? (
        <p className="pane px-3 py-1.5 text-xs text-[var(--text-muted)]" role="status">
          {alerts.isError ? "○ Alerts unavailable" : "✓ No active alerts"}
        </p>
      ) : (
        <ul className="flex w-full flex-col gap-1.5">
          {shown.map((a) => (
            <AlertRow key={a.id} alert={a} onAck={(id) => ack.mutate(id)} pending={ack.isPending && ack.variables === a.id} />
          ))}
        </ul>
      )}
      {(hidden > 0 || expanded) && sorted.length > VISIBLE && (
        <button type="button" className="pane px-3 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--text)]" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show less" : `+ ${hidden} more alert${hidden > 1 ? "s" : ""}`}
        </button>
      )}
    </section>
  );
}
