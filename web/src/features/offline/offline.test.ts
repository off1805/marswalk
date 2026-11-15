/**
 * Tests de la feature F7 — hors ligne.
 *
 * On teste les modules purs (sans React, sans navigateur) :
 *   operationQueue.ts  enfilage, suppression, rejeu, MAX_ATTEMPTS
 *   prefetch.ts        buildPrefetchList (structure des URLs)
 *
 * Les hooks React (useNetworkStatus, useOfflineQueue, usePrefetch)
 * sont testés par intégration dans offline.test.tsx.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { OperationQueue, buildReplayHandlers, type ReplayHandler, type Storage } from "./operationQueue";
import { pointAhead } from "./FieldReportPanel";
import { buildPrefetchList } from "./prefetch";
import type { QueuedOperation } from "./types";
import type { SiteManifest } from "@/shared/api/client";

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Implémentation en mémoire de Storage pour les tests. */
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
}

function makeQueue(
  handlers?: Map<QueuedOperation["kind"], ReplayHandler>,
): OperationQueue {
  return new OperationQueue(
    new MemoryStorage(),
    handlers ?? new Map(),
  );
}

// ── OperationQueue — enfilage ─────────────────────────────────────────────────

describe("OperationQueue.enqueue", () => {
  it("ajoute une opération avec les bons champs", () => {
    const queue = makeQueue();
    const op = queue.enqueue("createTarget", { name: "T1" });

    expect(op.kind).toBe("createTarget");
    expect(op.payload).toEqual({ name: "T1" });
    expect(op.attempts).toBe(0);
    expect(typeof op.id).toBe("string");
    expect(op.id.length).toBeGreaterThan(0);
  });

  it("persiste dans le stockage", () => {
    const queue = makeQueue();
    queue.enqueue("createTarget", { name: "T1" });
    expect(queue.size()).toBe(1);
  });

  it("plusieurs enfilages s'accumulent", () => {
    const queue = makeQueue();
    queue.enqueue("createTarget", { name: "T1" });
    queue.enqueue("updateTarget", { id: "T2", position: [77.58, 18.38] });
    queue.enqueue("deleteTarget", "T3");
    expect(queue.size()).toBe(3);
  });

  it("chaque opération a un identifiant unique", () => {
    const queue = makeQueue();
    const a = queue.enqueue("createTarget", {});
    const b = queue.enqueue("createTarget", {});
    expect(a.id).not.toBe(b.id);
  });
});

// ── OperationQueue — suppression ──────────────────────────────────────────────

describe("OperationQueue.remove", () => {
  it("retire l'opération demandée", () => {
    const queue = makeQueue();
    const op = queue.enqueue("createTarget", {});
    queue.remove(op.id);
    expect(queue.size()).toBe(0);
  });

  it("ne retire que l'opération ciblée", () => {
    const queue = makeQueue();
    const a = queue.enqueue("createTarget", {});
    queue.enqueue("deleteTarget", "T2");
    queue.remove(a.id);
    expect(queue.size()).toBe(1);
    expect(queue.load()[0]?.kind).toBe("deleteTarget");
  });

  it("ne lève pas d'erreur si l'ID est inconnu", () => {
    const queue = makeQueue();
    expect(() => queue.remove("inexistant")).not.toThrow();
  });
});

// ── OperationQueue — rejeu (succès) ──────────────────────────────────────────

describe("OperationQueue.replayAll — succès", () => {
  it("retire les opérations réussies de la file", async () => {
    const handler = vi.fn().mockResolvedValue(undefined);
    const handlers = new Map<QueuedOperation["kind"], ReplayHandler>([
      ["createTarget", handler],
    ]);
    const queue = makeQueue(handlers);
    queue.enqueue("createTarget", { name: "T1" });

    const results = await queue.replayAll();

    expect(results).toHaveLength(1);
    expect(results[0]?.kind).toBe("success");
    expect(queue.size()).toBe(0);
  });

  it("appelle le handler avec l'opération complète", async () => {
    const handler = vi.fn().mockResolvedValue(undefined);
    const handlers = new Map<QueuedOperation["kind"], ReplayHandler>([
      ["createTarget", handler],
    ]);
    const queue = makeQueue(handlers);
    queue.enqueue("createTarget", { name: "T1" });

    await queue.replayAll();

    expect(handler).toHaveBeenCalledOnce();
    expect((handler.mock.calls[0]![0] as QueuedOperation).kind).toBe("createTarget");
  });

  it("rejoue plusieurs opérations dans l'ordre d'enfilage", async () => {
    const order: string[] = [];
    const handlers = new Map<QueuedOperation["kind"], ReplayHandler>([
      ["createTarget", vi.fn().mockImplementation(async (op: QueuedOperation) => {
        order.push(op.payload as string);
      })],
    ]);
    const queue = makeQueue(handlers);
    queue.enqueue("createTarget", "premier");
    queue.enqueue("createTarget", "deuxième");
    queue.enqueue("createTarget", "troisième");

    await queue.replayAll();

    expect(order).toEqual(["premier", "deuxième", "troisième"]);
    expect(queue.size()).toBe(0);
  });

  it("retourne un tableau vide si la file est vide", async () => {
    const queue = makeQueue();
    const results = await queue.replayAll();
    expect(results).toEqual([]);
  });
});

// ── OperationQueue — rejeu (échec) ────────────────────────────────────────────

describe("OperationQueue.replayAll — échec", () => {
  it("incrémente le compteur de tentatives en cas d'échec", async () => {
    const handler = vi.fn().mockRejectedValue(new Error("réseau"));
    const handlers = new Map<QueuedOperation["kind"], ReplayHandler>([
      ["createTarget", handler],
    ]);
    const queue = makeQueue(handlers);
    queue.enqueue("createTarget", {});

    await queue.replayAll();

    expect(queue.size()).toBe(1);
    expect(queue.load()[0]?.attempts).toBe(1);
  });

  it("retire l'opération après MAX_ATTEMPTS (3) tentatives", async () => {
    const handler = vi.fn().mockRejectedValue(new Error("erreur permanente"));
    const handlers = new Map<QueuedOperation["kind"], ReplayHandler>([
      ["createTarget", handler],
    ]);
    const queue = makeQueue(handlers);
    queue.enqueue("createTarget", {});

    // 3 rejeux
    await queue.replayAll();
    await queue.replayAll();
    const results = await queue.replayAll();

    expect(queue.size()).toBe(0);
    expect(results[0]?.kind).toBe("failure");
    expect(results[0] && "reason" in results[0] && results[0].reason).toContain("Abandonné");
  });

  it("retire et signale une opération sans handler", async () => {
    const queue = makeQueue(); // aucun handler
    queue.enqueue("createTarget", {});

    const results = await queue.replayAll();

    expect(queue.size()).toBe(0);
    expect(results[0]?.kind).toBe("failure");
  });
});

// ── buildPrefetchList ─────────────────────────────────────────────────────────

const MOCK_MANIFEST: SiteManifest = {
  schema_version: "1.0",
  site_id: "fictif",
  name: "Site fictif",
  bbox: [77.56, 18.37, 77.60, 18.40],
  analysis_crs: "+proj=eqc +R=3396190",
  grid: { resolution_m: 2, width: 2000, height: 2000, transform: [1, 0, 0, 0, -1, 0] },
  habitat: [77.578, 18.381],
  mission_epoch_utc: "2026-01-01T00:00:00Z",
  default_preset: "safety",
  layers: [
    {
      id: "hillshade",
      title: "Ombrage",
      kind: "derived",
      source: { instrument: "SYNTHETIC", mission: "fictif" },
      status: "ok",
      tiles: { path: "tiles/hillshade/{z}/{x}/{y}.webp", minzoom: 12, maxzoom: 17, format: "webp", tile_size: 256 },
    },
    {
      id: "rover_traverse",
      title: "Traversée rover",
      kind: "vector",
      source: { instrument: "SYNTHETIC", mission: "fictif" },
      status: "ok",
      vector: "vector/rover_traverse.geojson",
    },
    {
      id: "crism_minerals",
      title: "Minéralogie",
      kind: "spectral",
      source: { instrument: "SYNTHETIC", mission: "fictif" },
      status: "ok",
      tiles: { path: "tiles/crism_minerals/{z}/{x}/{y}.webp", minzoom: 12, maxzoom: 15, format: "webp", tile_size: 256 },
    },
  ],
  terrain: { path: "tiles/terrain_rgb/{z}/{x}/{y}.png", minzoom: 12, maxzoom: 15, format: "png", tile_size: 256 },
};

describe("buildPrefetchList", () => {
  beforeEach(() => {
    // Pas d'effets de bord sur le DOM
  });

  it("inclut l'URL du manifeste", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    expect(list.some((r) => r.url === "/api/sites/fictif")).toBe(true);
  });

  it("inclut les couches vectorielles", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    expect(list.some((r) => r.url.includes("rover_traverse"))).toBe(true);
  });

  it("inclut les tuiles de hillshade aux niveaux de zoom définis", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    const hillshade = list.filter((r) => r.url.includes("hillshade"));
    expect(hillshade.length).toBeGreaterThan(0);
    // Tous les URLs contiennent le bon format
    hillshade.forEach((r) => expect(r.url).toContain(".webp"));
  });

  it("n'inclut pas les couches hors préréglage sécurité", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    // crism_minerals n'est pas dans SAFETY_LAYERS
    expect(list.some((r) => r.url.includes("crism_minerals"))).toBe(false);
  });

  it("inclut les tuiles terrain-RGB pour la vue 3D", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    expect(list.some((r) => r.url.includes("terrain_rgb"))).toBe(true);
  });

  it("retourne un tableau non vide", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    expect(list.length).toBeGreaterThan(0);
  });

  it("toutes les ressources ont une URL valide", () => {
    const list = buildPrefetchList(MOCK_MANIFEST, "fictif");
    list.forEach((r) => {
      expect(r.url).toMatch(/^\//);
    });
  });
});

// ── Relevés de terrain (E3) ───────────────────────────────────────────────────

describe("pointAhead", () => {
  const profile = [0, 20, 40, 60, 80].map((d) => ({ distance_m: d, position: [d, 0] })) as unknown as Parameters<
    typeof pointAhead
  >[0];

  it("prend le premier point du profil au moins à la distance demandée devant", () => {
    expect(pointAhead(profile, 15, 30)).toEqual([60, 0]);
  });

  it("retombe sur la fin du tracé près de l'arrivée", () => {
    expect(pointAhead(profile, 70, 50)).toEqual([80, 0]);
  });

  it("renvoie null sans profil", () => {
    expect(pointAhead([], 0, 50)).toBeNull();
  });
});

describe("rejeu d'une observation", () => {
  it("poste sur la sortie notée dans l'opération, sans l'envoyer dans le corps", async () => {
    const { api } = await import("@/shared/api/client");
    const post = vi.spyOn(api, "POST").mockResolvedValue({ data: {}, error: undefined } as never);
    const handler = buildReplayHandlers().get("addObservation")!;
    await handler({
      id: "op",
      kind: "addObservation",
      enqueuedAt: 0,
      attempts: 0,
      payload: { eva_id: "eva-7", position: [1, 2], note: "Litage" },
    });
    expect(post).toHaveBeenCalledWith("/api/eva/{eva_id}/observations", {
      params: { path: { eva_id: "eva-7" } },
      body: { position: [1, 2], note: "Litage" },
    });
    post.mockRestore();
  });
});
