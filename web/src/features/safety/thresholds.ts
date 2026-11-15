/**
 * Niveaux, seuils et mises en forme du panneau sécurité (F4).
 *
 * Les niveaux des jauges reprennent les règles du moteur d'alertes (A3,
 * api/marswalk_api/services/a3/rules.py) pour que la jauge et l'alerte passent à l'orange
 * ou au rouge au même moment. Les seuils réglables viennent de SafetySettings ; les autres
 * sont les hypothèses de conception d'A3, recopiées ici.
 */
import type { Alert, AlertLevel, SafetySettings } from "@/shared/api/client";

/** Durée d'une heure martienne (1/24 de sol), en secondes terrestres. */
export const MARS_HOUR_S = 88775.244 / 24;
/** Coucher du Soleil en heure solaire moyenne locale (hypothèse A3). */
export const SUNSET_LMST_H = 18.0;
export const RESERVE_CAUTION_MARGIN_PCT = 10;
export const DOSE_CAUTION_FRACTION = 0.8;
export const DUST_CAUTION_FRACTION = 0.8;
export const DOSE_RATE_CAUTION_USV_H = 30;
export const DOSE_RATE_DANGER_USV_H = 50;
export const PNR_CAUTION_S = 900;
export const DAYLIGHT_CAUTION_S = 3700;
export const DAYLIGHT_DANGER_S = 1850;

/** « ok » quand tout va bien, sinon le niveau d'alerte atteint. */
export type GaugeLevel = "ok" | AlertLevel;

/** Niveau d'une grandeur qui doit rester haute (réserve, consommables). */
export function levelBelow(value: number | null | undefined, caution: number, danger: number): GaugeLevel {
  if (value == null || Number.isNaN(value)) return "ok";
  if (value < danger) return "danger";
  if (value < caution) return "caution";
  return "ok";
}

/** Niveau d'une grandeur qui doit rester basse (dose, opacité, débit de dose). */
export function levelAbove(value: number | null | undefined, caution: number, danger: number): GaugeLevel {
  if (value == null || Number.isNaN(value)) return "ok";
  if (value >= danger) return "danger";
  if (value >= caution) return "caution";
  return "ok";
}

export function consumableLevel(pct: number | null | undefined, s: Pick<SafetySettings, "min_reserve_pct">): GaugeLevel {
  return levelBelow(pct, s.min_reserve_pct + RESERVE_CAUTION_MARGIN_PCT, s.min_reserve_pct);
}

export function doseLevel(doseUsv: number | null | undefined, s: Pick<SafetySettings, "max_dose_usv">): GaugeLevel {
  return levelAbove(doseUsv, s.max_dose_usv * DOSE_CAUTION_FRACTION, s.max_dose_usv);
}

export function doseRateLevel(rate: number | null | undefined): GaugeLevel {
  return levelAbove(rate, DOSE_RATE_CAUTION_USV_H, DOSE_RATE_DANGER_USV_H);
}

export function dustLevel(tau: number | null | undefined, s: Pick<SafetySettings, "max_dust_tau">): GaugeLevel {
  return levelAbove(tau, s.max_dust_tau * DUST_CAUTION_FRACTION, s.max_dust_tau);
}

export function pnrLevel(seconds: number | null | undefined): GaugeLevel {
  if (seconds == null || Number.isNaN(seconds)) return "ok";
  if (seconds <= 0) return "danger";
  return seconds < PNR_CAUTION_S ? "caution" : "ok";
}

export function daylightLevel(seconds: number | null | undefined): GaugeLevel {
  return levelBelow(seconds, DAYLIGHT_CAUTION_S, DAYLIGHT_DANGER_S);
}

/** Temps avant le coucher du Soleil, en secondes (négatif la nuit), comme A3. */
export function daylightLeftS(lmstHours: number): number {
  return (SUNSET_LMST_H - lmstHours) * MARS_HOUR_S;
}

const LEVEL_RANK: Record<AlertLevel, number> = { danger: 0, caution: 1, info: 2 };

/**
 * Ordre d'affichage du bandeau : non acquittées d'abord, puis danger, attention,
 * information, puis la plus récente.
 */
export function sortAlerts(alerts: Alert[]): Alert[] {
  return [...alerts].sort(
    (a, b) =>
      Number(a.acknowledged) - Number(b.acknowledged) ||
      LEVEL_RANK[a.level] - LEVEL_RANK[b.level] ||
      b.utc.localeCompare(a.utc),
  );
}

/** Ajoute ou remplace une alerte dans une liste, par identifiant. */
export function upsertAlert(list: Alert[] | undefined, alert: Alert): Alert[] {
  const rest = (list ?? []).filter((a) => a.id !== alert.id);
  return [alert, ...rest];
}

/** Durée en clair : « 1 h 30 min », « 12 min 05 s », « 45 s ». Négative : « dépassé ». */
export function formatCountdown(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  if (seconds <= 0) return "exceeded";
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")} min`;
  if (m > 0) return `${m} min ${String(sec).padStart(2, "0")} s`;
  return `${sec} s`;
}

/** Number formatted with fixed decimal places. */
export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Heure UTC « HH:MM:SS UTC » d'un instant ISO. */
export function formatUtc(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.toISOString().slice(11, 19)} UTC`;
}

/** Heures décimales en « HH:MM:SS ». */
export function formatHours(hours: number): string {
  const total = Math.round((((hours % 24) + 24) % 24) * 3600) % 86400;
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

export interface ClockAnchor {
  utc: string;
  sol: number;
  lmstHours: number;
  /** Instant local (ms) où l'ancre a été reçue. */
  receivedAt: number;
}

export interface ClockReading {
  utc: Date;
  sol: number;
  lmstHours: number;
  lmst: string;
}

/**
 * Avance l'horloge martienne depuis une ancre reçue du serveur, à vitesse réelle : un sol
 * dure 88 775 s, donc l'heure locale avance de 1/MARS_HOUR_S heure par seconde.
 */
export function advanceClock(anchor: ClockAnchor, nowMs: number): ClockReading {
  const dt = Math.max(0, (nowMs - anchor.receivedAt) / 1000);
  const hours = anchor.lmstHours + dt / MARS_HOUR_S;
  const rollover = Math.floor(hours / 24);
  const lmstHours = hours - rollover * 24;
  return {
    utc: new Date(new Date(anchor.utc).getTime() + dt * 1000),
    sol: anchor.sol + rollover,
    lmstHours,
    lmst: formatHours(lmstHours),
  };
}

/** « HH:MM:SS » en heures décimales. */
export function parseLmst(lmst: string): number | null {
  const m = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(lmst);
  if (!m) return null;
  return Number(m[1]) + Number(m[2]) / 60 + Number(m[3] ?? 0) / 3600;
}

/** Erreurs de cohérence des seuils saisis, par champ. */
export function validateSettings(s: SafetySettings): Partial<Record<keyof SafetySettings, string>> {
  const errors: Partial<Record<keyof SafetySettings, string>> = {};
  if (!(s.max_slope_deg > 0 && s.max_slope_deg <= 45)) errors.max_slope_deg = "Must be between 0 and 45°.";
  if (!(s.penalty_slope_deg >= 0 && s.penalty_slope_deg < s.max_slope_deg))
    errors.penalty_slope_deg = "Must be less than the forbidden slope.";
  if (!(s.min_reserve_pct >= 0 && s.min_reserve_pct <= 90)) errors.min_reserve_pct = "Must be between 0 and 90%.";
  if (!(s.max_dust_tau > 0 && s.max_dust_tau <= 10)) errors.max_dust_tau = "Must be between 0 and 10.";
  if (!(s.max_dose_usv > 0)) errors.max_dose_usv = "Must be positive.";
  if (!(s.min_illumination >= 0 && s.min_illumination <= 1)) errors.min_illumination = "Must be between 0 and 1.";
  return errors;
}
