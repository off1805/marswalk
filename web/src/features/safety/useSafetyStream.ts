/**
 * WebSocket /ws/eva/{eva_id} (A3) : range chaque message à sa place, dès réception.
 * - `alert`, `alert_cleared` : liste des alertes dans le cache (clé alerts(evaId)) ;
 * - `conditions` : conditions du moment dans le cache (clé conditionsCurrent) ;
 * - `telemetry`, `budget` : magasin local de F4 ;
 * - `route_updated` : le plan est relu.
 * Chaque enveloppe porte UTC, sol et heure locale : elle recale l'horloge martienne.
 * La connexion se rétablit seule, avec une attente croissante plafonnée à 10 s.
 */
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { evaSocketUrl, type Alert, type Conditions, type WsMessage } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { useSafety } from "./safetyStore";
import { parseLmst, upsertAlert } from "./thresholds";

const MAX_BACKOFF_MS = 10_000;

/** Applique un message du WebSocket ; exporté pour les tests. */
export function applyMessage(msg: WsMessage, client: QueryClient, evaId: string, siteId: string): void {
  const safety = useSafety.getState();
  const lmstHours = parseLmst(msg.lmst);
  if (lmstHours != null) safety.setAnchor({ utc: msg.utc, sol: msg.sol, lmstHours, receivedAt: Date.now() });
  const alertsKey = queryKeys.alerts(evaId);
  switch (msg.type) {
    case "alert":
      client.setQueryData<Alert[]>(alertsKey, (list) => upsertAlert(list, msg.payload as Alert));
      safety.markAlert();
      break;
    case "alert_cleared":
      client.setQueryData<Alert[]>(alertsKey, (list) => list?.filter((a) => a.id !== msg.payload.alert_id));
      break;
    case "conditions":
      client.setQueryData<Conditions>(queryKeys.conditionsCurrent(siteId), msg.payload);
      break;
    case "telemetry":
      safety.setTelemetry(msg.payload);
      break;
    case "budget":
      safety.setBudget(msg.payload);
      break;
    case "route_updated":
      void client.invalidateQueries({ queryKey: ["plans"] });
      break;
  }
}

export function useSafetyStream(): void {
  const evaId = useShared((s) => s.evaId);
  const siteId = useShared((s) => s.siteId);
  const client = useQueryClient();

  useEffect(() => {
    const { setStatus, reset } = useSafety.getState();
    if (!evaId) {
      reset();
      return;
    }
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    const connect = () => {
      setStatus("connecting");
      socket = new WebSocket(evaSocketUrl(evaId));
      socket.onopen = () => {
        attempt = 0;
        setStatus("open");
      };
      socket.onmessage = (event: MessageEvent) => {
        try {
          applyMessage(JSON.parse(String(event.data)) as WsMessage, client, evaId, siteId);
        } catch {
          // Message illisible : ignoré, le suivant recale l'état.
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        setStatus("closed");
        const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempt);
        attempt += 1;
        timer = setTimeout(connect, delay);
      };
    };
    connect();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
      reset();
    };
  }, [evaId, siteId, client]);
}
