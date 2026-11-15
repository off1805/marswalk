/**
 * Observe l'état du service worker Workbox.
 *
 * Principe S : ce hook ne fait qu'écouter les événements de `workbox-window`
 * et traduire les états en `SwStatus`. Il ne connaît ni la file ni l'UI.
 */
import { useEffect, useState } from "react";
import type { SwStatus } from "./types";

/** Retourne l'état observable du service worker. */
export function useSwStatus(): SwStatus {
  const [status, setStatus] = useState<SwStatus>(() => {
    if (!("serviceWorker" in navigator)) return "unsupported";
    return "pending";
  });

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    // Lecture de l'état initial depuis la registration existante
    void navigator.serviceWorker.getRegistration().then((reg) => {
      if (!reg) return;
      if (reg.active) setStatus("active");
      else if (reg.waiting) setStatus("waiting");
    });

    // Écoute des changements d'état
    const handleControllerChange = () => setStatus("active");
    navigator.serviceWorker.addEventListener(
      "controllerchange",
      handleControllerChange,
    );
    return () => {
      navigator.serviceWorker.removeEventListener(
        "controllerchange",
        handleControllerChange,
      );
    };
  }, []);

  return status;
}
