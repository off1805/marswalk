/**
 * Relevés de terrain pendant la sortie (écart E3, étape 11 du scénario de démo).
 *
 * Deux actions, affichées sous le panneau « Sécurité » tant qu'une sortie est suivie :
 *   - « Signaler un obstacle » : POST /api/eva/{id}/obstacles, quelques dizaines de mètres
 *     devant l'astronaute sur son tracé ; l'API recalcule le contournement local. Demande le
 *     réseau : le détour doit venir du serveur.
 *   - « Noter l'observation » : POST /api/eva/{id}/observations à la position courante. Sans
 *     réseau (ou si l'envoi échoue), l'observation part dans la file hors ligne de F7 et sera
 *     rejouée au retour de la connexion.
 *
 * Vit dans F7 parce que la file lui appartient (une fonctionnalité n'importe pas le code d'une
 * autre). Lit la sortie et le plan dans le cache partagé (shared/queryKeys).
 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Eva, type LonLat, type Plan, type Schemas } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { Button, Panel } from "@/shared/ui";
import { useNetworkStatus } from "./useNetworkStatus";
import { useOfflineQueue } from "./useOfflineQueue";

/** Distance, le long du tracé, entre l'astronaute et l'obstacle signalé. */
export const OBSTACLE_AHEAD_M = 50;
export const OBSTACLE_RADIUS_M = 6;

type RouteProfile = Schemas["Route"]["profile"];

/** Point du profil situé `aheadM` mètres après `doneM`, ou le dernier point du tracé. */
export function pointAhead(profile: RouteProfile, doneM: number, aheadM: number): LonLat | null {
  if (!profile.length) return null;
  const p = profile.find((pt) => pt.distance_m >= doneM + aheadM) ?? profile[profile.length - 1]!;
  return p.position as LonLat;
}

type Status = { tone: "ok" | "warn"; text: string } | null;

export function FieldReportPanel() {
  const evaId = useShared((s) => s.evaId);
  const activePlanId = useShared((s) => s.activePlanId);
  const qc = useQueryClient();
  const network = useNetworkStatus();
  const { enqueue } = useOfflineQueue();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"obstacle" | "observation" | null>(null);
  const [status, setStatus] = useState<Status>(null);

  if (!evaId) return null;
  const offline = network === "offline";

  /** État de la sortie : frais si le réseau répond, sinon celui du cache. */
  async function currentEva(id: string): Promise<Eva | undefined> {
    if (!offline) {
      try {
        const { data } = await api.GET("/api/eva/{eva_id}", { params: { path: { eva_id: id } } });
        if (data) {
          qc.setQueryData(queryKeys.eva(id), data);
          return data as Eva;
        }
      } catch {
        /* réseau coupé : on retombe sur le cache */
      }
    }
    return qc.getQueryData<Eva>(queryKeys.eva(id));
  }

  async function reportObstacle(id: string) {
    setBusy("obstacle");
    setStatus(null);
    try {
      const eva = await currentEva(id);
      if (!eva) throw new Error("Astronaut position unknown");
      const plan = qc.getQueryData<Plan>(queryKeys.plan(eva.plan_id ?? activePlanId ?? ""));
      const route = plan?.routes.find((r) => r.id === eva.route_id);
      const position =
        (route && pointAhead(route.profile, eva.distance_done_m, OBSTACLE_AHEAD_M)) ?? (eva.position as LonLat);
      const { data, error } = await api.POST("/api/eva/{eva_id}/obstacles", {
        params: { path: { eva_id: id } },
        body: { position, radius_m: OBSTACLE_RADIUS_M, note: note.trim() || null },
      });
      if (error || !data) throw new Error("The server did not accept the report");
      setStatus({
        tone: "ok",
        text: data.route
          ? `✓ Obstacle reported, route recomputed in ${Math.round(data.compute_time_ms ?? 0)} ms`
          : "✓ Obstacle reported, clear of the remaining route",
      });
      void qc.invalidateQueries({ queryKey: queryKeys.logbook(id) });
      void qc.invalidateQueries({ queryKey: queryKeys.eva(id) });
    } catch (err) {
      setStatus({ tone: "warn", text: `▲ ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setBusy(null);
    }
  }

  async function addObservation(id: string) {
    const text = note.trim();
    if (!text) return;
    setBusy("observation");
    setStatus(null);
    const eva = await currentEva(id);
    if (!eva) {
      setStatus({ tone: "warn", text: "▲ Astronaut position unknown: observation not logged" });
      setBusy(null);
      return;
    }
    const body: Schemas["ObservationCreate"] = {
      position: eva.position as LonLat,
      note: text,
      utc: new Date().toISOString(),
    };
    let sent = false;
    if (!offline) {
      try {
        const { error } = await api.POST("/api/eva/{eva_id}/observations", {
          params: { path: { eva_id: id } },
          body,
        });
        sent = !error;
      } catch {
        sent = false;
      }
    }
    if (sent) {
      setStatus({ tone: "ok", text: "✓ Observation added to the logbook" });
      void qc.invalidateQueries({ queryKey: queryKeys.logbook(id) });
    } else {
      enqueue("addObservation", { eva_id: id, ...body });
      setStatus({ tone: "warn", text: "◌ Offline: observation queued, it will be sent when the network is back" });
    }
    setNote("");
    setBusy(null);
  }

  return (
    <Panel title="Field reports">
      <div className="flex flex-col gap-2 text-sm">
        <label className="flex flex-col gap-1">
          Note
          <textarea
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Cross-bedding, loose boulder…"
            className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-[var(--text)]"
          />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="danger"
            disabled={busy !== null || offline}
            title={offline ? "The detour is computed by the server: network required" : undefined}
            onClick={() => void reportObstacle(evaId)}
          >
            {busy === "obstacle" ? "Reporting…" : "⚠ Report an obstacle"}
          </Button>
          <Button
            variant="primary"
            disabled={busy !== null || !note.trim()}
            onClick={() => void addObservation(evaId)}
          >
            {busy === "observation" ? "Sending…" : "✎ Log observation"}
          </Button>
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          The obstacle is placed {OBSTACLE_AHEAD_M} m ahead of you on the route (radius {OBSTACLE_RADIUS_M} m). The note
          goes with the obstacle, or becomes an observation at your position.
        </p>
        {status && (
          <p role="status" className={status.tone === "ok" ? "" : "font-semibold"}>
            {status.text}
          </p>
        )}
      </div>
    </Panel>
  );
}
