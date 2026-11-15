/**
 * Préchargement du paquet de site — côté React.
 *
 * Principe S : ce hook ne gère que l'état de progression du préchargement.
 * La logique de construction de la liste et de mise en cache est dans
 * `prefetch.ts`.
 */
import { useCallback, useRef, useState } from "react";
import { useSiteManifest } from "@/shared/hooks";
import { useShared } from "@/shared/store";
import { buildPrefetchList, prefetchResources } from "./prefetch";
import type { PrefetchProgress } from "./types";

const IDLE: PrefetchProgress = { done: 0, total: 0, running: false, error: null };

export interface PrefetchControls {
  progress: PrefetchProgress;
  /** Taille totale estimée en octets. */
  estimatedBytes: number;
  /** Lance le préchargement. */
  start: () => void;
  /** Annule le préchargement en cours. */
  cancel: () => void;
}

export function usePrefetch(): PrefetchControls {
  const { data: manifest } = useSiteManifest();
  const siteId = useShared((s) => s.siteId);
  const [progress, setProgress] = useState<PrefetchProgress>(IDLE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(() => {
    if (!manifest || progress.running) return;

    const resources = buildPrefetchList(manifest, siteId);
    const controller = new AbortController();
    abortRef.current = controller;

    void prefetchResources(resources, setProgress, controller.signal).catch(
      (err: unknown) => {
        if ((err as { name?: string }).name !== "AbortError") {
          setProgress((p) => ({
            ...p,
            running: false,
            error: err instanceof Error ? err.message : "Erreur inconnue",
          }));
        }
      },
    );
  }, [manifest, siteId, progress.running]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setProgress(IDLE);
  }, []);

  const estimatedBytes =
    manifest
      ? buildPrefetchList(manifest, siteId).reduce((s, r) => s + r.bytes, 0)
      : 0;

  return { progress, estimatedBytes, start, cancel };
}
