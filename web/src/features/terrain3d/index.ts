/**
 * Vue 3D (F6) — terrain martien en trois dimensions avec survol de l'itinéraire.
 *
 * Architecture (principes SOLID) :
 *
 *   terrain.config.ts   S+O  Configuration du décodage de l'altitude (injectable)
 *   flyover.ts          S    Calculs purs d'animation de caméra (sans React)
 *   routeLayer.ts       S    Construction de la PathLayer deck.gl
 *   useTerrain3dData.ts S+I  Hook de données (manifeste + itinéraire)
 *   useFlyover.ts       S    Hook d'état de l'animation
 *   TerrainCanvas.tsx   S+D  Rendu deck.gl (reçoit des abstractions, pas des stores)
 *   FlyoverControls.tsx S+I  Contrôles UI (reçoit exactement ce dont il a besoin)
 *   Terrain3dView.tsx   S+D  Assembleur : compose les pièces, ne calcule rien
 *
 * Ne jamais importer le code d'une autre fonctionnalité (features/<autre>/).
 * Communication via @/shared/store (magasin partagé) et @/shared/api/client.
 */
import type { Feature } from "@/app/feature";
import { Terrain3dView } from "./Terrain3dView";

export const feature: Feature = {
  id: "terrain3d",
  panels: [],
  routes: [
    {
      path: "/3d",
      component: Terrain3dView,
    },
  ],
};
