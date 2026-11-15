/**
 * Exécution des commandes vocales.
 *
 * Principe S : exécuter une commande est sa seule responsabilité.
 *   Le parsing est dans `commandParser.ts`.
 *   La reconnaissance est dans `useVoiceRecognition.ts`.
 *
 * Principe D : reçoit `SpeechQueue` (abstraction), pas un synthétiseur concret.
 *
 * Communication uniquement via le magasin partagé et TanStack Query —
 * jamais en important une autre feature.
 */
import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { useShared } from "@/shared/store";
import { queryKeys } from "@/shared/queryKeys";
import { api, type Alert } from "@/shared/api/client";
import type { VoiceCommand } from "./types";
import type { SpeechQueue } from "./useSpeechQueue";

/** Retour humain après exécution d'une commande. */
const FEEDBACK: Partial<Record<VoiceCommand["kind"], string>> = {
  addTarget: "Mode ajout de cible activé. Cliquez sur la carte.",
  returnToHabitat: "Recalcul de l'itinéraire vers l'habitat.",
  acknowledgeAlert: "Alerte acquittée.",
  startFlyover: "Lancement du survol.",
  pauseFlyover: "Survol en pause.",
  queryPoint: "Interrogation du point en cours.",
  unknown: "Commande non reconnue.",
};

export function useVoiceCommands(speechQueue: SpeechQueue) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const setPickMode = useShared((s) => s.setPickMode);
  const setActiveRoute = useShared((s) => s.setActiveRoute);
  const activePlanId = useShared((s) => s.activePlanId);
  const evaId = useShared((s) => s.evaId);
  const siteId = useShared((s) => s.siteId);

  const execute = useCallback(
    async (cmd: VoiceCommand) => {
      const feedback = FEEDBACK[cmd.kind];

      switch (cmd.kind) {
        // ── Ajouter une cible ───────────────────────────────────────────────
        case "addTarget":
          setPickMode("addTarget");
          break;

        // ── Choisir une variante ────────────────────────────────────────────
        case "selectVariant": {
          if (!activePlanId) {
            speechQueue.enqueue({
              text: "Aucun plan actif pour choisir une variante.",
              priority: "low",
            });
            return;
          }
          const plan = qc.getQueryData(queryKeys.plan(activePlanId)) as
            | { routes: { id: string; variant: string }[] }
            | undefined;
          const route = plan?.routes.find((r) => r.variant === cmd.variant);
          if (!route) {
            speechQueue.enqueue({
              text: `Variante ${cmd.variant} indisponible.`,
              priority: "low",
            });
            return;
          }
          try {
            await api.PATCH("/api/plans/{plan_id}", {
              params: { path: { plan_id: activePlanId } },
              body: { selected_route_id: route.id },
            });
            setActiveRoute(route.id);
            const label =
              cmd.variant === "safest" ? "la plus sûre"
              : cmd.variant === "fastest" ? "la plus rapide"
              : "science";
            speechQueue.enqueue({
              text: `Variante ${label} sélectionnée.`,
              priority: "low",
            });
          } catch {
            speechQueue.enqueue({ text: "Échec de la sélection.", priority: "low" });
          }
          return;
        }

        // ── Interroger un point ─────────────────────────────────────────────
        case "queryPoint":
          setPickMode("query");
          break;

        // ── Survol 3D ───────────────────────────────────────────────────────
        case "startFlyover":
          void navigate("/3d");
          break;

        case "pauseFlyover":
          // La pause est gérée par F6 via un store local — on lui envoie
          // un signal via un événement DOM personnalisé (découplage léger).
          window.dispatchEvent(new CustomEvent("v1:flyover:pause"));
          break;

        case "setFlyoverSpeed":
          window.dispatchEvent(
            new CustomEvent("v1:flyover:speed", { detail: cmd.speed }),
          );
          break;

        // ── Retour à l'habitat ──────────────────────────────────────────────
        case "returnToHabitat": {
          if (!evaId) {
            speechQueue.enqueue({
              text: "Aucune sortie en cours.",
              priority: "low",
            });
            return;
          }
          try {
            await api.POST("/api/eva/{eva_id}/obstacles", {
              params: { path: { eva_id: evaId } },
              body: { position: [0, 0], radius_m: 0, note: "Retour forcé (commande vocale)" },
            });
            void qc.invalidateQueries({ queryKey: ["plans"] });
          } catch {
            /* silent */
          }
          break;
        }

        // ── Acquitter une alerte ────────────────────────────────────────────
        case "acknowledgeAlert": {
          const alerts = qc.getQueryData(queryKeys.alerts(evaId ?? undefined)) as
            | Alert[]
            | undefined;
          const first = alerts?.find((a) => !a.acknowledged);
          if (!first) {
            speechQueue.enqueue({ text: "Aucune alerte à acquitter.", priority: "low" });
            return;
          }
          try {
            await api.POST("/api/alerts/{alert_id}/ack", {
              params: { path: { alert_id: first.id } },
            });
            qc.setQueryData<Alert[]>(
              queryKeys.alerts(evaId ?? undefined),
              (list) =>
                list?.map((a) =>
                  a.id === first.id
                    ? { ...a, acknowledged: true, acknowledged_at: new Date().toISOString() }
                    : a,
                ),
            );
          } catch {
            /* silent */
          }
          break;
        }

        // ── Couche ─────────────────────────────────────────────────────────
        case "toggleLayer": {
          const { layers, setLayer } = useShared.getState();
          const current = layers[cmd.layerId];
          setLayer(cmd.layerId, { visible: !current?.visible });
          break;
        }

        case "unknown":
          // Pas de feedback vocal pour éviter de spammer si le micro capte du bruit
          return;
      }

      // Retour auditif
      if (feedback) {
        speechQueue.enqueue({ text: feedback, priority: "low" });
      }

      // Invalider les cibles si on vient d'en ajouter une
      if (cmd.kind === "addTarget") {
        void qc.invalidateQueries({ queryKey: queryKeys.targets(siteId) });
      }
    },
    [
      qc, navigate, setPickMode, setActiveRoute,
      activePlanId, evaId, siteId, speechQueue,
    ],
  );

  return { execute };
}
