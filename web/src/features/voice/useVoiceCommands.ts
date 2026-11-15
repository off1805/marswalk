/**
 * Exécution des commandes vocales.
 *
 * Principe S : exécuter une commande est sa seule responsabilité.
 * Principe D : reçoit SpeechQueue (abstraction).
 *
 * Tous les retours vocaux sont en anglais — cohérent avec la voix choisie.
 * Communication uniquement via le magasin partagé et TanStack Query.
 */
import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { useShared } from "@/shared/store";
import { queryKeys } from "@/shared/queryKeys";
import { api, type Alert } from "@/shared/api/client";
import type { VoiceCommand } from "./types";
import type { SpeechQueue } from "./useSpeechQueue";

/** Retours vocaux en anglais pour chaque commande. */
const FEEDBACK: Partial<Record<VoiceCommand["kind"], string>> = {
  addTarget       : "Target placement mode activated. Click on the map to place it.",
  returnToHabitat : "Emergency return initiated. Recalculating route to habitat.",
  acknowledgeAlert: "Alert acknowledged.",
  startFlyover    : "Starting flyover. Switching to 3D view.",
  pauseFlyover    : "Flyover paused.",
  resumeFlyover   : "Flyover resumed.",
  queryPoint      : "Querying point data.",
  setFlyoverSpeed : "Speed updated.",
};

/** Messages quand la commande ne peut pas s'exécuter. */
const NO_CONTEXT: Partial<Record<VoiceCommand["kind"], string>> = {
  selectVariant   : "No active plan. Please plan a route first.",
  returnToHabitat : "No active EVA in progress.",
  acknowledgeAlert: "No unacknowledged alerts.",
};

export function useVoiceCommands(speechQueue: SpeechQueue) {
  const qc           = useQueryClient();
  const navigate     = useNavigate();
  const setPickMode  = useShared((s) => s.setPickMode);
  const setActiveRoute = useShared((s) => s.setActiveRoute);
  const activePlanId = useShared((s) => s.activePlanId);
  const evaId        = useShared((s) => s.evaId);
  const siteId       = useShared((s) => s.siteId);

  const execute = useCallback(
    async (cmd: VoiceCommand) => {
      switch (cmd.kind) {

        // ── Ajouter une cible ─────────────────────────────────────────────
        case "addTarget":
          setPickMode("addTarget");
          speechQueue.enqueue({ text: FEEDBACK.addTarget!, priority: "low" });
          void qc.invalidateQueries({ queryKey: queryKeys.targets(siteId) });
          break;

        // ── Choisir une variante ──────────────────────────────────────────
        case "selectVariant": {
          if (!activePlanId) {
            speechQueue.enqueue({ text: NO_CONTEXT.selectVariant!, priority: "low" });
            return;
          }
          const plan = qc.getQueryData(queryKeys.plan(activePlanId)) as
            | { routes: { id: string; variant: string }[] } | undefined;
          const route = plan?.routes.find((r) => r.variant === cmd.variant);
          if (!route) {
            speechQueue.enqueue({ text: `Variant ${cmd.variant} is not available.`, priority: "low" });
            return;
          }
          try {
            await api.PATCH("/api/plans/{plan_id}", {
              params: { path: { plan_id: activePlanId } },
              body: { selected_route_id: route.id },
            });
            setActiveRoute(route.id);
            const label =
              cmd.variant === "safest" ? "safest"
              : cmd.variant === "fastest" ? "fastest"
              : "science";
            speechQueue.enqueue({ text: `${label} route selected.`, priority: "low" });
          } catch {
            speechQueue.enqueue({ text: "Failed to select variant. Please try again.", priority: "low" });
          }
          return;
        }

        // ── Interroger un point ───────────────────────────────────────────
        case "queryPoint":
          setPickMode("query");
          speechQueue.enqueue({ text: FEEDBACK.queryPoint!, priority: "low" });
          break;

        // ── Survol 3D ─────────────────────────────────────────────────────
        case "startFlyover":
          speechQueue.enqueue({ text: FEEDBACK.startFlyover!, priority: "low" });
          void navigate("/3d");
          break;

        case "pauseFlyover":
          window.dispatchEvent(new CustomEvent("v1:flyover:pause"));
          speechQueue.enqueue({ text: FEEDBACK.pauseFlyover!, priority: "low" });
          break;

        case "resumeFlyover":
          window.dispatchEvent(new CustomEvent("v1:flyover:resume"));
          speechQueue.enqueue({ text: FEEDBACK.resumeFlyover!, priority: "low" });
          break;

        case "setFlyoverSpeed":
          window.dispatchEvent(new CustomEvent("v1:flyover:speed", { detail: cmd.speed }));
          speechQueue.enqueue({ text: `Speed set to ${cmd.speed}x.`, priority: "low" });
          break;

        // ── Retour à l'habitat ────────────────────────────────────────────
        case "returnToHabitat": {
          if (!evaId) {
            speechQueue.enqueue({ text: NO_CONTEXT.returnToHabitat!, priority: "low" });
            return;
          }
          speechQueue.enqueue({ text: FEEDBACK.returnToHabitat!, priority: "high" });
          try {
            await api.POST("/api/eva/{eva_id}/obstacles", {
              params: { path: { eva_id: evaId } },
              body: { position: [0, 0], radius_m: 0, note: "Emergency return (voice command)" },
            });
            void qc.invalidateQueries({ queryKey: ["plans"] });
          } catch { /* silent */ }
          break;
        }

        // ── Acquitter une alerte ──────────────────────────────────────────
        case "acknowledgeAlert": {
          const alerts = qc.getQueryData(queryKeys.alerts(evaId ?? undefined)) as Alert[] | undefined;
          const first = alerts?.find((a) => !a.acknowledged);
          if (!first) {
            speechQueue.enqueue({ text: NO_CONTEXT.acknowledgeAlert!, priority: "low" });
            return;
          }
          try {
            await api.POST("/api/alerts/{alert_id}/ack", {
              params: { path: { alert_id: first.id } },
            });
            qc.setQueryData<Alert[]>(queryKeys.alerts(evaId ?? undefined), (list) =>
              list?.map((a) =>
                a.id === first.id
                  ? { ...a, acknowledged: true, acknowledged_at: new Date().toISOString() }
                  : a,
              ),
            );
            speechQueue.enqueue({ text: FEEDBACK.acknowledgeAlert!, priority: "low" });
          } catch { /* silent */ }
          break;
        }

        // ── Couche ────────────────────────────────────────────────────────
        case "toggleLayer": {
          const { layers, setLayer } = useShared.getState();
          const current = layers[cmd.layerId];
          setLayer(cmd.layerId, { visible: !current?.visible });
          const action = current?.visible ? "hidden" : "shown";
          speechQueue.enqueue({ text: `Layer ${cmd.layerId} ${action}.`, priority: "low" });
          break;
        }

        case "unknown":
          // Pas de feedback pour le bruit ambiant
          break;
      }
    },
    [qc, navigate, setPickMode, setActiveRoute, activePlanId, evaId, siteId, speechQueue],
  );

  return { execute };
}
