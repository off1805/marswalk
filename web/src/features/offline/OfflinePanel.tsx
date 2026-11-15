/**
 * Panneau principal F7 — slot `map-overlay` (coin supérieur droit).
 *
 * Principe S : ce composant orchestre les sous-panneaux. Il ne calcule
 * rien et ne contient pas de logique métier.
 *
 * Principe D : dépend des abstractions exposées par ses hooks, pas de
 * leurs implémentations.
 */
import { useNetworkStatus } from "./useNetworkStatus";
import { useOfflineQueue } from "./useOfflineQueue";
import { usePrefetch } from "./usePrefetch";
import { useSwStatus } from "./useSwStatus";
import { NetworkBadge } from "./NetworkBadge";
import { PrefetchPanel } from "./PrefetchPanel";
import { QueueStatusPanel } from "./QueueStatusPanel";
import { useState } from "react";

export function OfflinePanel() {
  const network = useNetworkStatus();
  const swStatus = useSwStatus();
  const { pending, pendingCount, replaying, lastResults } = useOfflineQueue();
  const prefetch = usePrefetch();
  const [expanded, setExpanded] = useState(false);

  const cacheAvailable =
    swStatus === "active" && "caches" in window;

  // N'afficher que le badge quand tout va bien
  const hasActivity =
    network === "offline" ||
    pendingCount > 0 ||
    prefetch.progress.running ||
    lastResults.length > 0;

  return (
    <div className="absolute right-4 top-4 flex flex-col items-end gap-2 z-10">
      {/* Badge réseau — toujours visible */}
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="rounded-full"
        aria-expanded={expanded}
        aria-label="Open offline panel"
      >
        <NetworkBadge status={network} pendingCount={pendingCount} />
      </button>

      {/* Panneau étendu */}
      {(expanded || hasActivity) && (
        <div className="flex w-72 flex-col gap-2">
          <PrefetchPanel
            {...prefetch}
            cacheAvailable={cacheAvailable}
          />
          <QueueStatusPanel
            pending={pending}
            replaying={replaying}
            lastResults={lastResults}
          />
        </div>
      )}
    </div>
  );
}
