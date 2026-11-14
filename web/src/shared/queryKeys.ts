/**
 * Clés TanStack Query partagées (gelées avec contrats-v1). Toute donnée serveur passe par
 * ces clés, pour que deux fonctionnalités qui lisent la même ressource partagent le cache.
 */
export const queryKeys = {
  health: () => ["health"] as const,
  time: (siteId: string) => ["time", siteId] as const,
  sites: () => ["sites"] as const,
  site: (siteId: string) => ["sites", siteId] as const,
  presets: () => ["presets"] as const,
  vector: (siteId: string, layerId: string) => ["sites", siteId, "vector", layerId] as const,
  query: (siteId: string, lon: number, lat: number) => ["sites", siteId, "query", lon, lat] as const,
  hazards: (siteId: string, preset?: string) => ["sites", siteId, "hazards", preset ?? null] as const,
  settings: (siteId: string) => ["sites", siteId, "settings"] as const,
  targets: (siteId: string) => ["sites", siteId, "targets"] as const,
  plan: (planId: string) => ["plans", planId] as const,
  conditionsCurrent: (siteId: string) => ["sites", siteId, "conditions", "current"] as const,
  conditionsForecast: (siteId: string, hours: number) =>
    ["sites", siteId, "conditions", "forecast", hours] as const,
  scenarios: () => ["scenarios"] as const,
  alerts: (evaId?: string) => ["alerts", evaId ?? null] as const,
  eva: (evaId: string) => ["eva", evaId] as const,
  groundImages: (siteId: string) => ["sites", siteId, "ground-images"] as const,
  logbook: (evaId: string) => ["eva", evaId, "logbook"] as const,
} as const;
