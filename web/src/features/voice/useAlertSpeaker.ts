/**
 * Lit les alertes danger à voix haute dès leur apparition dans le cache.
 *
 * Principe S : surveiller les alertes et les lire est sa seule responsabilité.
 *
 * Principe D : ne dépend pas de F4. Lit le cache TanStack Query directement
 * sous la clé `queryKeys.alerts(evaId)` — le même mécanisme que F4 (consigne
 * 9 de la fiche F2 : écouter via le cache sans dépendre d'une autre feature).
 */
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShared } from "@/shared/store";
import { queryKeys } from "@/shared/queryKeys";
import type { Alert } from "@/shared/api/client";
import type { SpeechQueue } from "./useSpeechQueue";

/** Texte lu à voix haute selon le niveau d'alerte. */
function alertToSpeech(alert: Alert): string {
  const level =
    alert.level === "danger" ? "Alerte danger"
    : alert.level === "caution" ? "Attention"
    : "Information";
  return `${level}. ${alert.title}. ${alert.action}.`;
}

export function useAlertSpeaker(speechQueue: SpeechQueue): void {
  const qc = useQueryClient();
  const evaId = useShared((s) => s.evaId);
  // Suivi des alertes déjà lues pour éviter les répétitions
  const spokenIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Réinitialiser quand la sortie change
    spokenIds.current = new Set();
  }, [evaId]);

  useEffect(() => {
    if (!evaId) return;

    const unsubscribe = qc.getQueryCache().subscribe((event) => {
      if (event.type !== "updated") return;

      const key = queryKeys.alerts(evaId);
      const isAlertsKey =
        JSON.stringify(event.query.queryKey) === JSON.stringify(key);
      if (!isAlertsKey) return;

      const alerts = event.query.state.data as Alert[] | undefined;
      if (!alerts) return;

      for (const alert of alerts) {
        if (alert.acknowledged) continue;
        if (spokenIds.current.has(alert.id)) continue;

        spokenIds.current.add(alert.id);

        // Les alertes danger interrompent la synthèse en cours
        speechQueue.enqueue({
          text: alertToSpeech(alert),
          priority: alert.level === "danger" ? "high" : "low",
        });
      }
    });

    return unsubscribe;
  }, [evaId, qc, speechQueue]);
}
