/**
 * État local de F4 : dernier état reçu par le WebSocket de la sortie (télémétrie, budget,
 * horodatage martien) et état de la connexion. Les alertes et les conditions vont dans le
 * cache TanStack Query, sous les clés partagées, pour que les autres vues les voient.
 */
import { create } from "zustand";
import type { Schemas } from "@/shared/api/client";
import type { ClockAnchor } from "./thresholds";

export type Telemetry = Schemas["TelemetryPayload"];
export type Budget = Schemas["BudgetPayload"];
export type StreamStatus = "idle" | "connecting" | "open" | "closed";

export interface Received<T> {
  value: T;
  /** Instant local (ms) de réception, pour faire tourner les comptes à rebours. */
  receivedAt: number;
}

interface SafetyState {
  status: StreamStatus;
  telemetry: Received<Telemetry> | null;
  budget: Received<Budget> | null;
  /** Dernier horodatage martien reçu (enveloppe WebSocket). */
  anchor: ClockAnchor | null;
  /** Instant local (ms) de réception de la dernière alerte, pour mesurer l'affichage. */
  lastAlertAt: number | null;
  setStatus: (status: StreamStatus) => void;
  setTelemetry: (value: Telemetry) => void;
  setBudget: (value: Budget) => void;
  setAnchor: (anchor: ClockAnchor) => void;
  markAlert: () => void;
  reset: () => void;
}

const empty = { status: "idle" as const, telemetry: null, budget: null, anchor: null, lastAlertAt: null };

export const useSafety = create<SafetyState>()((set) => ({
  ...empty,
  setStatus: (status) => set({ status }),
  setTelemetry: (value) => set({ telemetry: { value, receivedAt: Date.now() } }),
  setBudget: (value) => set({ budget: { value, receivedAt: Date.now() } }),
  setAnchor: (anchor) => set({ anchor }),
  markAlert: () => set({ lastAlertAt: Date.now() }),
  reset: () => set(empty),
}));
