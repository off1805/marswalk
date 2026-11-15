/**
 * Gère la file d'attente des opérations hors ligne côté React.
 *
 * Principe S : ce hook coordonne la file et le réseau. Il ne connaît
 * pas l'UI.
 *
 * Principe D : reçoit l'instance `OperationQueue` via un singleton
 * du module `serviceRegistry` — pas instancié ici.
 */
import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import type { QueuedOperation, ReplayResult } from "./types";
import { getQueue } from "./serviceRegistry";
import { useNetworkStatus } from "./useNetworkStatus";

export interface OfflineQueueState {
  /** Opérations actuellement en file. */
  pending: QueuedOperation[];
  /** Nombre d'opérations en file. */
  pendingCount: number;
  /** Vrai si un rejeu est en cours. */
  replaying: boolean;
  /** Résultats du dernier rejeu. */
  lastResults: ReplayResult[];
  /** Mettre manuellement une opération en file. */
  enqueue: (kind: QueuedOperation["kind"], payload: unknown) => void;
}

/**
 * Le hook sert à plusieurs panneaux (badge réseau, relevés de terrain) : le rejeu est gardé
 * au niveau du module, pour qu'une opération ne soit jamais rejouée deux fois, et chaque
 * instance est prévenue quand une autre modifie la file.
 */
let replayingGlobal = false;
const subscribers = new Set<() => void>();
function notifyAll(): void {
  for (const fn of [...subscribers]) fn();
}

export function useOfflineQueue(): OfflineQueueState {
  const qc = useQueryClient();
  const siteId = useShared((s) => s.siteId);
  const network = useNetworkStatus();
  const queue = getQueue();

  const [pending, setPending] = useState<QueuedOperation[]>(() => queue.load());
  const [replaying, setReplaying] = useState(false);
  const [lastResults, setLastResults] = useState<ReplayResult[]>([]);

  /** Rafraîchit la liste locale depuis le stockage. */
  const refresh = useCallback(() => {
    setPending(queue.load());
  }, [queue]);

  useEffect(() => {
    subscribers.add(refresh);
    return () => {
      subscribers.delete(refresh);
    };
  }, [refresh]);

  /** Lance le rejeu dès le retour du réseau, une seule fois à la fois. */
  useEffect(() => {
    if (network !== "online" || replayingGlobal) return;
    const ops = queue.load();
    if (ops.length === 0) return;

    replayingGlobal = true;
    setReplaying(true);

    void queue.replayAll().then((results) => {
      setLastResults(results);
      replayingGlobal = false;
      notifyAll();
      setReplaying(false);

      // Invalider les caches TanStack Query concernés
      const hasTargetOp = results.some((r) =>
        r.kind === "success" &&
        ops.find((o) => o.id === r.operationId)?.kind.toLowerCase().includes("target"),
      );
      if (hasTargetOp) {
        void qc.invalidateQueries({ queryKey: queryKeys.targets(siteId) });
      }
    });
  }, [network, queue, refresh, qc, siteId]);

  const enqueue = useCallback(
    (kind: QueuedOperation["kind"], payload: unknown) => {
      queue.enqueue(kind, payload);
      notifyAll();
    },
    [queue],
  );

  return {
    pending,
    pendingCount: pending.length,
    replaying,
    lastResults,
    enqueue,
  };
}
