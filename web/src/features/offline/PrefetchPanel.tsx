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
      aria-label="Préchargement hors ligne"
    >
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
        Hors ligne — Préchargement
      </h3>

      {!cacheAvailable && (
        <p className="mb-2 text-xs text-[var(--text-caution)]">
          ▲ Service worker non actif — le préchargement nécessite un build de
          production.
        </p>
      )}

      {/* Description */}
      <p className="mb-2 text-xs text-[var(--text-muted)]">
        Téléchargez le paquet de site pour utiliser Marswalk sans connexion.
        {estimatedBytes > 0 && ` Taille estimée : ${formatBytes(estimatedBytes)}.`}
      </p>

      {/* Barre de progression */}
      {(running || complete) && (
        <div className="mb-2 space-y-1">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-2)]"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Progression du préchargement"
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
              ? "✓ Préchargement terminé"
              : `${done} / ${total} ressources (${percent} %)`}
          </p>
        </div>
      )}

      {/* Erreur */}
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
            aria-label="Lancer le préchargement du site"
          >
            ↓ Télécharger pour hors ligne
          </Button>
        )}
        {running && (
          <Button
            onClick={cancel}
            className="text-xs"
            aria-label="Annuler le préchargement"
          >
            ✕ Annuler
          </Button>
        )}
        {complete && (
          <Button
            onClick={start}
            className="text-xs"
            aria-label="Mettre à jour le cache"
          >
            ↻ Mettre à jour
          </Button>
        )}
      </div>
    </section>
  );
}
