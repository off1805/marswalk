# F7 — Hors ligne (PWA)

Rend Marswalk utilisable sans connexion : service worker Workbox, préchargement du paquet de site, indicateur réseau, file d'attente des modifications.

## Architecture (principes SOLID)

```
offline/
├── types.ts               Interfaces et types du module (I)
├── operationQueue.ts      Moteur de file persistante, injectable et extensible (S + O)
├── prefetch.ts            Logique de préchargement, pure et injectable (S + D)
├── serviceRegistry.ts     Composition root des singletons (D)
├── swRegistration.ts      Enregistrement du service worker dans setup() (S)
├── vite.ts                Plugin Vite PWA (S)
├── useNetworkStatus.ts    Hook — écoute online/offline uniquement (S + I)
├── useSwStatus.ts         Hook — état du service worker uniquement (S + I)
├── useOfflineQueue.ts     Hook — file d'attente + rejeu automatique (S + D)
├── usePrefetch.ts         Hook — progression du préchargement (S + I)
├── NetworkBadge.tsx       Badge réseau (reçoit ses props, n'observe pas le réseau) (S + I)
├── PrefetchPanel.tsx      Panneau préchargement (S + I)
├── QueueStatusPanel.tsx   Panneau file d'attente (S + I)
├── OfflinePanel.tsx       Assembleur des panneaux (S + D)
├── offline.test.ts        Tests unitaires des fonctions pures
└── index.ts               Export de la feature
```

## Principes SOLID appliqués

### S — Single Responsibility
Chaque fichier a une seule raison de changer :

| Fichier | Raison de changer |
|---|---|
| `operationQueue.ts` | Algorithme de file ou format de stockage |
| `prefetch.ts` | Liste des ressources à précharger |
| `serviceRegistry.ts` | Stratégie d'instanciation des singletons |
| `swRegistration.ts` | URL du service worker ou comportement d'activation |
| `vite.ts` | Configuration Workbox ou manifest PWA |
| `useNetworkStatus.ts` | API navigateur pour détecter le réseau |
| `useSwStatus.ts` | API navigateur pour l'état du SW |
| `useOfflineQueue.ts` | Déclenchement du rejeu ou invalidation TanStack Query |
| `usePrefetch.ts` | Déclenchement du préchargement |
| `NetworkBadge.tsx` | Apparence du badge réseau |
| `PrefetchPanel.tsx` | Ergonomie du panneau de préchargement |
| `QueueStatusPanel.tsx` | Affichage de la file d'attente |
| `OfflinePanel.tsx` | Assemblage des panneaux |

### O — Open/Closed
`OperationQueue` accepte une `Map<kind, ReplayHandler>` injectée. Ajouter le support de `addObstacle` revient à ajouter une entrée dans `buildReplayHandlers()` — le moteur de file ne change pas.

### L — Liskov
`MemoryStorage` (tests) et `localStorage` (production) respectent le même contrat `Storage`. L'`OperationQueue` fonctionne identiquement avec les deux.

### I — Interface Segregation
`PrefetchPanel` ne reçoit que `PrefetchControls`. `QueueStatusPanel` ne reçoit que `pending`, `replaying`, `lastResults`. Ni l'un ni l'autre ne reçoit l'état réseau ou l'état du SW.

### D — Dependency Inversion
`OperationQueue` dépend de `Storage` (interface) et de `ReplayHandler` (type fonction). `prefetchResources` reçoit `fetchFn` en paramètre. `OfflinePanel` dépend des abstractions exposées par ses hooks, pas de leur implémentation.

## Flux de données

```
navigator.onLine ──► useNetworkStatus ──► NetworkBadge
                                      ──► useOfflineQueue (déclenche replayAll)

localStorage ──► OperationQueue ──► useOfflineQueue ──► QueueStatusPanel
                                 └─ replayAll() ──► API (createTarget, etc.)
                                                 ──► queryClient.invalidate()

SiteManifest ──► buildPrefetchList ──► prefetchResources ──► Cache API
                                   ──► usePrefetch ──► PrefetchPanel
```

## Service worker

En production (`pnpm build`), `vite-plugin-pwa` génère `dist/sw.js` avec :
- Pré-cache du shell JS/CSS/HTML
- `NetworkFirst` pour `/api/**` (toujours fraîches si disponibles)
- `CacheFirst` pour `/tiles/**` (grandes, stables)

En développement (`pnpm dev:mock`), le plugin n'est pas actif pour ne pas
interférer avec le service worker de MSW.

## Critères d'acceptation

| Critère | Démonstration |
|---|---|
| PWA installable | Manifest dans `vite.ts`, `sw.js` généré au build |
| Préchargement avec progression | `PrefetchPanel` + `usePrefetch` + `prefetchResources` |
| Indicateur de connexion | `NetworkBadge` avec icône + texte (ENF-06) |
| File d'attente rejouée au retour réseau | `useOfflineQueue` → `replayAll()` au passage `offline → online` |
| Test : rejeu retire les succès | `offline.test.ts` — `OperationQueue.replayAll — succès` |
| Test : MAX_ATTEMPTS retire l'opération | `offline.test.ts` — `retire l'opération après 3 tentatives` |
