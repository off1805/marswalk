/**
 * Client HTTP typé, généré depuis contracts/openapi.json (pnpm gen:api).
 * Les coordonnées sont en degrés planétocentriques est, Mars 2000 (règle R2).
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type Schemas = components["schemas"];
export type SiteManifest = Schemas["SiteManifest"];
export type LayerInfo = Schemas["LayerInfo"];
export type Legend = Schemas["Legend"];
export type LonLat = [number, number];
export type Target = Schemas["Target"];
export type Plan = Schemas["Plan"];
export type Route = Schemas["Route"];
export type Alert = Schemas["Alert"];
export type AlertLevel = Schemas["AlertLevel"];
export type Conditions = Schemas["Conditions"];
export type Eva = Schemas["Eva"];
export type TimeInfo = Schemas["TimeInfo"];
export type DisplayPreset = Schemas["DisplayPreset"];
export type FeatureCollection = Schemas["FeatureCollection"];
export type PointQuery = Schemas["PointQuery"];
export type SafetySettings = Schemas["SafetySettings"];

/** Messages du WebSocket /ws/eva/{eva_id} : enveloppe { type, utc, sol, lmst, payload }. */
export type WsMessage =
  | Schemas["WsTelemetry"]
  | Schemas["WsAlert"]
  | Schemas["WsAlertCleared"]
  | Schemas["WsConditions"]
  | Schemas["WsRouteUpdated"]
  | Schemas["WsBudget"];

/** URL du WebSocket d'une sortie, relative à la page. */
export function evaSocketUrl(evaId: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/eva/${encodeURIComponent(evaId)}`;
}

/** Gabarit d'URL des tuiles d'une couche, pour MapLibre ou deck.gl. */
export function tileUrl(siteId: string, layerId: string, format: "webp" | "png"): string {
  return `/tiles/${siteId}/${layerId}/{z}/{x}/{y}.${format}`;
}
