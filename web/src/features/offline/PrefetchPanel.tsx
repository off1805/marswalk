/**
 * Panneau de préchargement du paquet de site.
 *
 * Principe S : afficher la progression et permettre de lancer/annuler
 * le préchargement est sa seule responsabilité.
 *
 * Principe I : reçoit exactement ce dont il a besoin via `PrefetchControls`.
 */
import { Button } from "@/shared/ui/Button";
import type { PrefetchControls } from "./usePrefetch";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "—";
  if (bytes < 1_000_000) return `${Math.round(bytes / 1000)} ko`;
  return `${(bytes / 1_000_000).toFixed(1)} Mo`;
}

interface Props extends PrefetchControls {
  /** Vrai si un service worker actif peut effectivement mettre en cache. */
  cacheAvailable: boolean;
}

export function PrefetchPanel({
  progress,
  estimatedBytes,
  cacheAvailable,
  start,
  cancel,
}: Props) {
  const { done, total, running, error } = progress;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  const complete = !running && done > 0 && done === total;

  return (
    <section
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
      aria-label="Offline prefetch"
    >
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
        Offline — Prefetch
      </h3>

      {!cacheAvailable && (
        <p className="mb-2 text-xs text-[var(--text-caution)]">
          ▲ Service worker not active — prefetch requires a production build.
        </p>
      )}

      {/* Description */}
      <p className="mb-2 text-xs text-[var(--text-muted)]">
        Download the site package to use Marswalk offline.
        {estimatedBytes > 0 && ` Estimated size: ${formatBytes(estimatedBytes)}.`}
      </p>

      {/* Progress bar */}
      {(running || complete) && (
        <div className="mb-2 space-y-1">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-2)]"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Prefetch progress"
          >
            <div
              className={`h-full rounded-full transition-all ${
                complete
                  ? "bg-[var(--color-ok)]"
                  : "bg-[var(--color-info)]"
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-xs text-[var(--text-muted)]" aria-live="polite">
            {complete
              ? "✓ Prefetch complete"
              : `${done} / ${total} resources (${percent}%)`}
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="mb-2 text-xs text-[var(--text-danger)]" role="alert">
          ⛔ {error}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {!running && !complete && (
          <Button
            variant="primary"
            onClick={start}
            disabled={!cacheAvailable}
            className="text-xs"
            aria-label="Start site prefetch"
          >
            ↓ Download for offline
          </Button>
        )}
        {running && (
          <Button
            onClick={cancel}
            className="text-xs"
            aria-label="Cancel prefetch"
          >
            ✕ Cancel
          </Button>
        )}
        {complete && (
          <Button
            onClick={start}
            className="text-xs"
            aria-label="Update cache"
          >
            ↻ Update
          </Button>
        )}
      </div>
    </section>
  );
}
