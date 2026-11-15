# PR : [F2] Cibles et itinéraire

## Résumé

Implémentation complète de la feature F2 : ajout/déplacement/suppression de cibles sur la carte, zones interdites et pénalisées, comparateur de variantes d'itinéraire, point de non-retour, recalcul automatique avec debounce.

## Fichiers modifiés

| Fichier | Rôle |
|---|---|
| `web/src/features/targets/index.ts` | Export `feature`, couches deck.gl (`mapLayers`), injection QueryClient |
| `web/src/features/targets/TargetsPanel.tsx` | Panneau `right` : liste des cibles, bouton d'ajout, indicateur de calcul, comparateur |
| `web/src/features/targets/TargetCard.tsx` | Fiche d'une cible avec édition et suppression |
| `web/src/features/targets/RouteComparator.tsx` | Comparateur des trois variantes (`safest`, `fastest`, `science`) |
| `web/src/features/targets/TargetsOverlay.tsx` | Overlay `map-overlay` : légende des zones |
| `web/src/features/targets/HazardOverlay.tsx` | Légende + tooltip de survol des zones |
| `web/src/features/targets/layers.ts` | Couches deck.gl (cibles, zones, itinéraires, PNR, étiquettes) |
| `web/src/features/targets/targetsStore.ts` | Zustand local : hover de zone, drag en cours |
| `web/src/features/targets/useTargets.ts` | Hooks TanStack Query pour toutes les mutations |
| `web/src/features/targets/useAutoPlan.ts` | Recalcul automatique debounce 400 ms + AbortController |
| `web/src/features/targets/targets.test.tsx` | 8 tests (voir section Tests ci-dessous) |
| `web/src/features/targets/README.md` | Documentation de la feature |
| `tasks/change-requests/F2-pickmode-map-click.md` | Demande de changement de contrat |

## Critères d'acceptation

### 1. Le tracé se met à jour seul après le déplacement d'une cible

`useAutoPlan` observe le tableau de cibles via TanStack Query. Chaque changement déclenche un debounce de 400 ms, puis un `POST /api/sites/{siteId}/plans`. La règle « dernière demande gagne » est appliquée via un compteur de séquence (`reqCounterRef`) et un `AbortController`.

**Démontré par :** test « Debounce du recalcul automatique » — deux déplacements rapides ne déclenchent qu'un seul `POST /api/sites/{siteId}/plans`.

### 2. L'astronaute garde la main : aucune variante n'est imposée

`useAutoPlan` ne sélectionne jamais de route automatiquement (`setActiveRoute(null)` forcé). Le `RouteComparator` n'appelle `setActiveRoute` que sur action explicite de l'utilisateur.

**Démontré par :** test « RouteComparator > n'en sélectionne aucune automatiquement » — aucun badge « Choisie » visible à l'initialisation.

### 3. Chaque variante explique pourquoi elle passe là

Chaque `RouteCard` affiche `route.explanation` (tronçon par tronçon) dans un `<details>` dépliable, et `route.warnings` en liste visible.

**Démontré par :** test « RouteComparator > affiche les trois variantes safest, fastest, science » — les trois articles sont présents avec leurs métriques et leurs explications.

## Tests (8 au total)

| # | Test | Ce qu'il vérifie |
|---|---|---|
| 1 | Ajout d'une cible | `POST /api/sites/{siteId}/targets` appelé avec le bon body |
| 2 | Déplacement d'une cible | `PATCH /api/targets/{id}` appelé avec la nouvelle position |
| 3 | Suppression d'une cible | `DELETE /api/targets/{id}` appelé |
| 4 | Debounce du recalcul | Un seul `POST /api/sites/{siteId}/plans` après deux modifications rapides |
| 5 | RouteComparator : trois variantes | Les articles `safest`, `fastest`, `science` sont présents |
| 6 | RouteComparator : aucune sélection auto | Aucun badge « Choisie » à l'init |
| 7 | Sélection d'une variante | `PATCH /api/plans/{id}` appelé avec `selected_route_id` correct |
| 8 | TargetsPanel : liste visible | Les cibles pré-chargées s'affichent dans la liste |

## Demande de changement de contrat

`tasks/change-requests/F2-pickmode-map-click.md` : ajouter un mécanisme dans `MapView` et `store.ts` (gelés) pour transmettre les clics carte aux fonctionnalités en mode `addTarget`.

**Contournement actuel :** couche deck.gl `GeoJsonLayer` transparente couvrant la bbox du site. Quand `pickMode = "addTarget"`, deck.gl capture le clic via `onClick` et transmet `info.coordinate` au callback interne de F2.

## Exigences couvertes

- **EF-04** : ajout, déplacement, suppression de cibles ; fiche d'objectif, de mesure et de temps de travail
- **EF-05** : trois variantes calculées et affichées ; choix de variante par l'astronaute
- **ENF-12** : recalcul automatique après toute modification, avec indicateur de calcul

## Vérifications

- ✅ `tsc --noEmit` : aucune erreur
- ✅ `pnpm lint` : aucune erreur ESLint
- ✅ `pnpm test` : 108 tests passent (8 nouveaux pour F2 + 100 existants)
- ✅ `pnpm build` : build Vite réussi
- ✅ `python tools/check_ownership.py` : 13 fichiers dans le périmètre de F2
- ✅ Contrats gelés inchangés (`contracts/`, `store.ts`, `registry.ts`, `feature.ts`, `queryKeys.ts`)
- ✅ `README.md` présent dans `web/src/features/targets/`
