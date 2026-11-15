/**
 * Feature hors ligne (F7) — PWA, préchargement, file d'attente.
 *
 * Architecture (principes SOLID) :
 *
 *   types.ts              I    Interfaces et types partagés du module
 *   operationQueue.ts     S+O  Moteur de file (pure, injectable, extensible)
 *   prefetch.ts           S+D  Logique de préchargement (pure, injectable)
 *   serviceRegistry.ts    D    Composition root des singletons du module
 *   swRegistration.ts     S    Enregistrement du service worker (setup())
 *   vite.ts               S    Configuration du plugin Vite PWA
 *   useNetworkStatus.ts   S+I  Hook réseau (écoute seulement)
 *   useSwStatus.ts        S+I  Hook état service worker
 *   useOfflineQueue.ts    S+D  Hook file d'attente + rejeu automatique
 *   usePrefetch.ts        S+I  Hook préchargement
 *   NetworkBadge.tsx      S+I  Badge réseau (reçoit ses props, ne lit pas le réseau)
 *   PrefetchPanel.tsx     S+I  Panneau de préchargement
 *   QueueStatusPanel.tsx  S+I  Panneau de file d'attente
 *   OfflinePanel.tsx      S+D  Assembleur des panneaux (orchestre, ne calcule pas)
 *   FieldReportPanel.tsx  S    Obstacle et observation pendant la sortie (file hors ligne)
 *
 * Ne jamais importer le code d'une autre fonctionnalité.
 * Communication via @/shared/store et @/shared/api/client.
 */
import type { Feature } from "@/app/feature";
import { FieldReportPanel } from "./FieldReportPanel";
import { OfflinePanel } from "./OfflinePanel";
import { registerServiceWorker } from "./swRegistration";

export const feature: Feature = {
  id: "offline",
  panels: [
    {
      slot: "map-overlay",
      order: 30,
      component: OfflinePanel,
      modes: ["map"],
    },
    // Juste sous le panneau « Sécurité » de F4 (ordre 5), visible pendant une sortie.
    { slot: "right", order: 6, component: FieldReportPanel },
  ],
  routes: [],
  /** Enregistre le service worker Workbox au démarrage de l'application. */
  setup: registerServiceWorker,
};

// Export public pour les tests
export { OperationQueue, buildReplayHandlers } from "./operationQueue";
export { buildPrefetchList } from "./prefetch";
export { pointAhead } from "./FieldReportPanel";
export { __setQueueForTest } from "./serviceRegistry";
