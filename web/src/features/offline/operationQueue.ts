/**
 * File d'attente persistante des opérations hors ligne.
 *
 * Principe S (Single Responsibility) : ce module gère uniquement la
 * persistance et le rejeu des opérations. Il ne connaît pas React, le
 * magasin Zustand ni l'état réseau.
 *
 * Principe O (Open/Closed) : les handlers de rejeu sont une `Map`
 * injectée — ajouter un type d'opération ne modifie pas `OperationQueue`.
 *
 * Principe D (Dependency Inversion) : `OperationQueue` dépend de
 * `ReplayHandler` (interface) et de `Storage` (interface), pas de
 * `localStorage` directement — ce qui rend le service testable.
 */
import type { QueuedOperation, ReplayResult } from "./types";

/** Stockage abstrait pour la persistance de la file. */
export interface Storage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/** Fonction qui rejoue une opération vers le serveur. */
export type ReplayHandler = (op: QueuedOperation) => Promise<void>;

const STORAGE_KEY = "f7:offline-queue";
const MAX_ATTEMPTS = 3;

/** Génère un identifiant unique simple. */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export class OperationQueue {
  private readonly storage: Storage;
  private readonly handlers: Map<QueuedOperation["kind"], ReplayHandler>;

  constructor(
    storage: Storage,
    handlers: Map<QueuedOperation["kind"], ReplayHandler>,
  ) {
    this.storage = storage;
    this.handlers = handlers;
  }

  /** Lit la file depuis le stockage. */
  load(): QueuedOperation[] {
    try {
      const raw = this.storage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return JSON.parse(raw) as QueuedOperation[];
    } catch {
      return [];
    }
  }

  /** Persiste la file dans le stockage. */
  private save(ops: QueuedOperation[]): void {
    this.storage.setItem(STORAGE_KEY, JSON.stringify(ops));
  }

  /** Ajoute une opération en fin de file et la persiste. */
  enqueue(
    kind: QueuedOperation["kind"],
    payload: unknown,
  ): QueuedOperation {
    const op: QueuedOperation = {
      id: generateId(),
      kind,
      enqueuedAt: Date.now(),
      payload,
      attempts: 0,
    };
    const ops = this.load();
    ops.push(op);
    this.save(ops);
    return op;
  }

  /** Retire une opération par son identifiant. */
  remove(id: string): void {
    const ops = this.load().filter((op) => op.id !== id);
    this.save(ops);
  }

  /** Retourne le nombre d'opérations en attente. */
  size(): number {
    return this.load().length;
  }

  /**
   * Rejoue toutes les opérations en attente dans l'ordre d'enfilage.
   *
   * - Les succès retirent l'opération de la file.
   * - Les échecs incrémentent le compteur de tentatives.
   * - Les opérations dépassant `MAX_ATTEMPTS` sont retirées de la file
   *   pour éviter un cycle infini.
   */
  async replayAll(): Promise<ReplayResult[]> {
    const ops = this.load();
    if (ops.length === 0) return [];

    const results: ReplayResult[] = [];

    for (const op of ops) {
      const handler = this.handlers.get(op.kind);
      if (!handler) {
        // Pas de handler connu : on retire l'opération obsolète
        this.remove(op.id);
        results.push({
          kind: "failure",
          operationId: op.id,
          reason: `No handler for operation "${op.kind}"`,
        });
        continue;
      }

      const updated: QueuedOperation = { ...op, attempts: op.attempts + 1 };

      try {
        await handler(op);
        this.remove(op.id);
        results.push({ kind: "success", operationId: op.id });
      } catch (err) {
        const reason = err instanceof Error ? err.message : String(err);
        if (updated.attempts >= MAX_ATTEMPTS) {
          this.remove(op.id);
          results.push({
            kind: "failure",
            operationId: op.id,
            reason: `Abandoned after ${MAX_ATTEMPTS} attempts: ${reason}`,
          });
        } else {
          // Mettre à jour le compteur de tentatives
          const remaining = this.load().map((o) =>
            o.id === op.id ? updated : o,
          );
          this.save(remaining);
          results.push({ kind: "failure", operationId: op.id, reason });
        }
      }
    }

    return results;
  }
}

/**
 * Fabrique les handlers de rejeu à partir du client API.
 * Principe D : injecté dans `OperationQueue`, pas codé en dur.
 */
export function buildReplayHandlers(): Map<
  QueuedOperation["kind"],
  ReplayHandler
> {
  const handlers = new Map<QueuedOperation["kind"], ReplayHandler>();

  handlers.set("createTarget", async (op) => {
    const { api } = await import("@/shared/api/client");
    const { useShared } = await import("@/shared/store");
    const siteId = useShared.getState().siteId;
    const { error } = await api.POST("/api/sites/{site_id}/targets", {
      params: { path: { site_id: siteId } },
      body: op.payload as import("@/shared/api/client").Schemas["TargetCreate"],
    });
    if (error) throw new Error("Failed to create target");
  });

  handlers.set("updateTarget", async (op) => {
    const { api } = await import("@/shared/api/client");
    const payload = op.payload as { id: string } & import("@/shared/api/client").Schemas["TargetUpdate"];
    const { id, ...patch } = payload;
    const { error } = await api.PATCH("/api/targets/{target_id}", {
      params: { path: { target_id: id } },
      body: patch as import("@/shared/api/client").Schemas["TargetUpdate"],
    });
    if (error) throw new Error("Failed to update target");
  });

  handlers.set("deleteTarget", async (op) => {
    const { api } = await import("@/shared/api/client");
    const { error } = await api.DELETE("/api/targets/{target_id}", {
      params: { path: { target_id: op.payload as string } },
    });
    if (error) throw new Error("Failed to delete target");
  });

  handlers.set("addObservation", async (op) => {
    const { api } = await import("@/shared/api/client");
    const { useShared } = await import("@/shared/store");
    const evaId = useShared.getState().evaId;
    if (!evaId) throw new Error("No active EVA");
    const { error } = await api.POST("/api/eva/{eva_id}/observations", {
      params: { path: { eva_id: evaId } },
      body: op.payload as import("@/shared/api/client").Schemas["ObservationCreate"],
    });
    if (error) throw new Error("Failed to add observation");
  });

  return handlers;
}
