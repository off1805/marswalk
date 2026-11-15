/**
 * Panneau « Sécurité » : horloge martienne, comptes à rebours (point de non-retour, coucher
 * du Soleil), jauges des consommables, de la dose et de la réserve au retour, et démarrage
 * d'une sortie simulée sur la variante active.
 */
import { useState } from "react";
import type { SafetySettings } from "@/shared/api/client";
import { useShared } from "@/shared/store";
import { Button, Panel } from "@/shared/ui";
import { useEva, usePlan, useScenarios, useSettings, useStartEva, useTime } from "./queries";
import { useSafety } from "./safetyStore";
import {
  advanceClock,
  consumableLevel,
  daylightLeftS,
  daylightLevel,
  doseLevel,
  formatCountdown,
  formatNumber,
  formatUtc,
  levelBelow,
  pnrLevel,
  RESERVE_CAUTION_MARGIN_PCT,
  type ClockAnchor,
} from "./thresholds";
import { Countdown, Gauge, useNow } from "./ui";

/** Seuils par défaut tant que le serveur n'a pas répondu (valeurs de SafetySettings). */
const FALLBACK: Pick<SafetySettings, "min_reserve_pct" | "max_dose_usv"> = { min_reserve_pct: 30, max_dose_usv: 1000 };

function useClockAnchor(): ClockAnchor | null {
  const time = useTime();
  const ws = useSafety((s) => s.anchor);
  const fromApi: ClockAnchor | null = time.data
    ? { utc: time.data.utc, sol: time.data.sol, lmstHours: time.data.lmst_hours, receivedAt: time.dataUpdatedAt }
    : null;
  if (ws && (!fromApi || ws.receivedAt >= fromApi.receivedAt)) return ws;
  return fromApi;
}

export function MarsClock({ now }: { now: number }) {
  const anchor = useClockAnchor();
  if (!anchor) return <p className="text-sm">Horloge martienne indisponible.</p>;
  const c = advanceClock(anchor, now);
  return (
    <div aria-label="Horloge martienne" className="flex flex-wrap items-baseline gap-x-3">
      <strong className="text-lg tabular-nums">Sol {c.sol}</strong>
      <strong className="text-lg tabular-nums">{c.lmst} LMST</strong>
      <span className="text-sm tabular-nums text-[var(--text-muted)]">{formatUtc(c.utc)}</span>
    </div>
  );
}

function StartEva() {
  const planId = useShared((s) => s.activePlanId);
  const routeId = useShared((s) => s.activeRouteId);
  const scenarios = useScenarios();
  const start = useStartEva();
  const [scenarioId, setScenarioId] = useState("");
  const [speed, setSpeed] = useState(10);
  const ready = !!planId && !!routeId;
  return (
    <div className="flex flex-col gap-2 border-t border-[var(--border)] pt-2">
      <p className="text-sm">
        Aucune sortie en cours.{" "}
        {ready ? "Les valeurs ci-dessus sont celles prévues par le plan." : "Choisissez une variante pour la démarrer."}
      </p>
      <label className="flex items-center justify-between gap-2 text-sm">
        Scénario
        <select
          className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-1"
          value={scenarioId}
          onChange={(e) => setScenarioId(e.target.value)}
        >
          <option value="">Conditions du moment</option>
          {scenarios.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center justify-between gap-2 text-sm">
        Accélération
        <select
          className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-1"
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
        >
          {[1, 10, 30, 60].map((v) => (
            <option key={v} value={v}>
              × {v}
            </option>
          ))}
        </select>
      </label>
      <Button
        variant="primary"
        disabled={!ready || start.isPending}
        onClick={() => start.mutate({ planId: planId!, routeId: routeId!, scenarioId: scenarioId || null, speed })}
      >
        {start.isPending ? "Démarrage…" : "Démarrer la sortie simulée"}
      </Button>
      {start.isError && <p className="text-sm">▲ {start.error.message}</p>}
    </div>
  );
}

const LIMITING: Record<string, string> = {
  oxygen: "oxygène",
  battery: "batterie",
  water: "eau",
  time: "temps",
  dose: "dose",
};

const STATUS_TEXT = {
  idle: "○ Pas de liaison",
  connecting: "◌ Connexion…",
  open: "● Temps réel",
  closed: "○ Liaison perdue, reconnexion…",
} as const;

export function SafetyPanel() {
  const now = useNow();
  const evaId = useShared((s) => s.evaId);
  const setEvaId = useShared((s) => s.setEvaId);
  const activeRouteId = useShared((s) => s.activeRouteId);
  const status = useSafety((s) => s.status);
  const telemetry = useSafety((s) => s.telemetry);
  const budget = useSafety((s) => s.budget);
  const eva = useEva();
  const plan = usePlan();
  const settingsQuery = useSettings();
  const s = { ...FALLBACK, ...settingsQuery.data };
  const anchor = useClockAnchor();
  const clock = anchor ? advanceClock(anchor, now) : null;

  const route = plan.data?.routes.find((r) => r.id === (activeRouteId ?? plan.data?.selected_route_id));
  const evaData = evaId ? eva.data : undefined;
  const live = telemetry?.value;
  const consumables = live?.consumables ?? evaData?.consumables ?? null;
  const dose = live?.dose_usv ?? evaData?.dose_usv ?? null;

  // Réserve et point de non-retour : budget du WebSocket, sinon sortie, sinon plan prévu.
  let reserve: number | null = null;
  let pnrS: number | null = null;
  let source: "live" | "eva" | "plan" | null = null;
  if (budget) {
    reserve = budget.value.reserve_pct;
    pnrS = budget.value.time_to_pnr_s == null ? null : budget.value.time_to_pnr_s - (now - budget.receivedAt) / 1000;
    source = "live";
  } else if (evaData) {
    reserve = evaData.reserve_pct ?? null;
    pnrS = evaData.time_to_pnr_s == null ? null : evaData.time_to_pnr_s - (now - eva.dataUpdatedAt) / 1000;
    source = "eva";
  } else if (route) {
    reserve = route.return_check.reserve_at_return_pct;
    pnrS = route.return_check.point_of_no_return_time_s ?? null;
    source = "plan";
  }
  const daylight = clock ? daylightLeftS(clock.lmstHours) : null;
  const reserveLevel = levelBelow(reserve, s.min_reserve_pct + RESERVE_CAUTION_MARGIN_PCT, s.min_reserve_pct);

  return (
    <Panel title="Sécurité">
      <div className="flex flex-col gap-3">
        <MarsClock now={now} />
        {evaId && (
          <p className="flex items-center justify-between text-sm" role="status">
            <span>
              Sortie {evaId} · {STATUS_TEXT[status]}
            </span>
            <button type="button" className="underline" onClick={() => setEvaId(null)}>
              Quitter le suivi
            </button>
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          <Countdown
            label="Point de non-retour"
            value={source === "plan" && pnrS != null ? `à ${formatCountdown(pnrS)}` : formatCountdown(pnrS)}
            level={source === "plan" ? "ok" : pnrLevel(pnrS)}
            hint={source === "plan" ? "prévu, après le départ" : pnrS == null ? "non calculé" : undefined}
          />
          <Countdown
            label="Coucher du Soleil"
            value={daylight == null ? "—" : daylight <= 0 ? "nuit" : formatCountdown(daylight)}
            level={daylightLevel(daylight)}
          />
        </div>
        <Gauge
          label="Réserve au retour"
          value={reserve == null ? "—" : `${formatNumber(reserve)} %`}
          pct={reserve}
          level={reserveLevel}
          hint={`minimum ${formatNumber(s.min_reserve_pct)} %${source === "plan" ? " · prévue par le plan" : ""}${
            budget ? ` · limitant : ${LIMITING[budget.value.limiting_consumable] ?? budget.value.limiting_consumable}` : ""
          }`}
        />
        {consumables && (
          <>
            <Gauge
              label="Oxygène"
              value={`${formatNumber(consumables.oxygen_pct)} %`}
              pct={consumables.oxygen_pct}
              level={consumableLevel(consumables.oxygen_pct, s)}
            />
            <Gauge
              label="Batterie"
              value={`${formatNumber(consumables.battery_pct)} %`}
              pct={consumables.battery_pct}
              level={consumableLevel(consumables.battery_pct, s)}
            />
            <Gauge
              label="Eau"
              value={`${formatNumber(consumables.water_pct)} %`}
              pct={consumables.water_pct}
              level={consumableLevel(consumables.water_pct, s)}
            />
          </>
        )}
        <Gauge
          label="Dose reçue"
          value={
            dose != null
              ? `${formatNumber(dose, 1)} µSv`
              : route
                ? `${formatNumber(route.totals.consumption.dose_usv, 1)} µSv prévus`
                : "—"
          }
          pct={dose != null ? (100 * dose) / s.max_dose_usv : null}
          level={doseLevel(dose ?? route?.totals.consumption.dose_usv, s)}
          hint={`maximum de la sortie ${formatNumber(s.max_dose_usv)} µSv`}
        />
        {!evaId && <StartEva />}
      </div>
    </Panel>
  );
}
