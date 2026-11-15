/**
 * Panneau d'état de la file d'attente hors ligne.
 *
 * Principe S : afficher les opérations en attente et les résultats
 * du dernier rejeu est sa seule responsabilité.
 *
 * Principe I : reçoit exactement ce dont il a besoin.
 */
import type { QueuedOperation, ReplayResult } from "./types";

const KIND_LABEL: Record<QueuedOperation["kind"], string> = {
  createTarget: "Create target",
  updateTarget: "Move target",
  deleteTarget: "Delete target",
  addObservation: "Observation",
};

interface Props {
  pending: QueuedOperation[];
  replaying: boolean;
  lastResults: ReplayResult[];
}

export function QueueStatusPanel({ pending, replaying, lastResults }: Props) {
  if (pending.length === 0 && lastResults.length === 0) return null;

  return (
    <section
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
      aria-label="Offline queue"
    >
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
        Queue
      </h3>

      {replaying && (
        <p
          className="mb-1 flex items-center gap-1 text-xs text-[var(--text-info)]"
          role="status"
          aria-live="polite"
        >
          <span className="inline-block animate-spin">⟳</span>
          Synchronizing…
        </p>
      )}

      {/* Pending operations */}
      {pending.length > 0 && (
        <ul className="mb-2 space-y-1" aria-label="Pending operations">
          {pending.map((op) => (
            <li
              key={op.id}
              className="flex items-center justify-between rounded bg-[var(--surface-2)] px-2 py-1 text-xs"
            >
              <span>{KIND_LABEL[op.kind] ?? op.kind}</span>
              <span className="text-[var(--text-muted)]">
                {op.attempts > 0 && `${op.attempts} attempt${op.attempts > 1 ? "s" : ""}`}
              </span>
            </li>
          ))}
        </ul>
      )}

      {/* Last replay results */}
      {lastResults.length > 0 && pending.length === 0 && (
        <p className="text-xs text-[var(--text-ok)]" role="status">
          ✓ {lastResults.filter((r) => r.kind === "success").length} operation
          {lastResults.length > 1 ? "s" : ""} synchronized
        </p>
      )}

      {lastResults.some((r) => r.kind === "failure") && (
        <ul className="mt-1 space-y-0.5" aria-label="Sync errors">
          {lastResults
            .filter((r): r is Extract<ReplayResult, { kind: "failure" }> =>
              r.kind === "failure",
            )
            .map((r) => (
              <li key={r.operationId} className="text-xs text-[var(--text-danger)]">
                ⛔ {r.reason}
              </li>
            ))}
        </ul>
      )}
    </section>
  );
}
