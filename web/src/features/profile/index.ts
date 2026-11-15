/**
 * Profil d'itinéraire (F3).
 *
 * - bottom : ProfilePanel, graphique ECharts altitude et pente, bandes de pente pénalisée et
 *   interdite, durées par tronçon, cibles et point de non-retour.
 * - couches deck.gl : repère à `hoverDistanceM` et capture du survol le long de l'itinéraire.
 *
 * Règle : ne jamais importer le code d'une autre fonctionnalité ; passer par le magasin
 * partagé (@/shared/store) ou par l'API (@/shared/api/client).
 */
import type { Feature } from "@/app/feature";
import { mapLayers } from "./mapLayers";
import { ProfilePanel } from "./ProfilePanel";

export const feature: Feature = {
  id: "profile",
  panels: [{ slot: "bottom", order: 10, component: ProfilePanel, modes: ["map"] }],
  mapLayers,
  routes: [],
};
