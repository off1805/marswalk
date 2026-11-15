/**
 * Détecte l'état de la connexion réseau.
 *
 * Principe S : ce hook ne fait qu'écouter les événements `online`/`offline`
 * du navigateur. Il ne connaît ni la file d'attente ni le service worker.
 */
import { useEffect, useState } from "react";
import type { NetworkStatus } from "./types";

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>(
    navigator.onLine ? "online" : "offline",
  );

  useEffect(() => {
    const handleOnline = () => setStatus("online");
    const handleOffline = () => setStatus("offline");

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return status;
}
