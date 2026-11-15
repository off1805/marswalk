/**
 * Vue 3D (F6) — terrain martien en trois dimensions avec survol de l'itinéraire.
 *
 * Architecture (principes SOLID) :
 *
 *   terrain.config.ts   S+O  Configuration du décodage de l'altitude (injectable)
 *   demProtocol.ts      S    Tuiles d'altitude relatives au site (protocole mwdem://)
 *   flyover.ts          S    Calculs purs d'animation (sans React)
 *   camera.ts           S    Caméra de poursuite et vues prédéfinies (MapLibre)
 *   useTerrain3dData.ts S+I  Hook de données (manifeste + itinéraire + cibles)
 *   useFlyover.ts       S    Hook d'état de l'animation
 *   TerrainCanvas.tsx   S+D  Rendu MapLibre : relief, ombrage, ciel, tracé
 *   FlyoverControls.tsx S+I  Barre de survol (lecture, curseur, vitesse)
 *   Terrain3dView.tsx   S+D  Assembleur : compose les pièces, ne calcule rien
 *
 * Ne jamais importer le code d'une autre fonctionnalité (features/<autre>/).
 * Communication via @/shared/store (magasin partagé) et @/shared/api/client.
 */
import { createElement, lazy, Suspense } from "react";
import type { Feature } from "@/app/feature";

// Loaded on demand: MapLibre's 3D terrain only weighs on the page when /3d is opened.
const LazyTerrain3dView = lazy(() => import("./Terrain3dView").then((m) => ({ default: m.Terrain3dView })));

function Terrain3dRoute() {
  return createElement(Suspense, { fallback: null }, createElement(LazyTerrain3dView));
}

export const feature: Feature = {
  id: "terrain3d",
  panels: [],
  routes: [
    {
      path: "/3d",
      component: Terrain3dRoute,
    },
  ],
};
