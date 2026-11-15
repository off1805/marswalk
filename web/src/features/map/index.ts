/**
 * Fonctionnalité Carte et couches (F1).
 *
 * Exporte la spécification de la fonctionnalité enregistrée dans `app/registry.ts`.
 * - Panneaux : Panneau de couches (gauche) et panneau d'interrogation au sol (droite).
 * - Overlay : Échelle martienne (règle R3).
 * - Couches cartographiques : Sources raster MapLibre synchronisées avec Zustand.
 */
import type { Feature } from "@/app/feature";
import { LayerPanel } from "./components/LayerPanel";
import { QueryPanel } from "./components/QueryPanel";
import { MarsScaleBar } from "./components/MarsScaleBar";
import { getMapSources } from "./sources";

export const feature: Feature = {
  id: "map",
  panels: [
    { slot: "left", order: 10, component: LayerPanel },
    { slot: "right", order: 10, component: QueryPanel },
    { slot: "map-overlay", order: 10, component: MarsScaleBar },
  ],
  mapSources: (ctx) => getMapSources(ctx),
  routes: [],
};

export { LayerPanel, QueryPanel, MarsScaleBar };
