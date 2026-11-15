# F2 — Cibles et itinéraire

Feature React du panneau de cibles et du comparateur de variantes de Marswalk.

## Périmètre

| Fichier | Rôle |
|---|---|
| `index.ts` | Export `feature`, couches deck.gl (`mapLayers`), injection du QueryClient |
| `TargetsPanel.tsx` | Panneau `right` : liste des cibles, bouton d'ajout, indicateur de calcul, comparateur |
| `TargetCard.tsx` | Fiche d'une cible : objectif, mesure, temps de travail, édition, suppression |
| `RouteComparator.tsx` | Comparateur des trois variantes (`safest`, `fastest`, `science`) |
| `TargetsOverlay.tsx` | Overlay `map-overlay` : légende des zones interdites/pénalisées |
| `HazardOverlay.tsx` | Légende et tooltip de survol des zones |
| `layers.ts` | Construction des couches deck.gl (cibles, zones, itinéraires, PNR) |
| `targetsStore.ts` | Zustand local : hover de zone, drag en cours |
| `useTargets.ts` | Hooks TanStack Query : cibles, plan, zones, mutations |
| `useAutoPlan.ts` | Recalcul automatique avec debounce 400 ms et AbortController |
| `targets.test.tsx` | Tests (voir ci-dessous) |

## Couches deck.gl

1. **Zone de capture de clics** (`f2-pick-area`) — GeoJsonLayer transparent, actif uniquement en `pickMode = addTarget`. Contournement du mécanisme absent dans `MapView` (voir `tasks/change-requests/F2-pickmode-map-click.md`).
2. **Zones interdites** (`f2-hazard-forbidden`) — GeoJsonLayer rouge-orange, `⛔ Interdite`, avec tooltip de cause au survol.
3. **Zones pénalisées** (`f2-hazard-penalized`) — GeoJsonLayer jaune, `▲ Pénalisée`, même comportement.
4. **Itinéraires** (`f2-route-{id}`) — PathLayer, une couche par variante. La variante active est plus épaisse et opaque.
5. **Point de non-retour** (`f2-pnr`) — TextLayer `⏱ PNR` sur la position de `return_check.point_of_no_return`.
6. **Cibles** (`f2-targets`) — ScatterplotLayer pickable. Clic → sélection/désélection. La cible sélectionnée est plus grande.
7. **Étiquettes** (`f2-target-labels`, `f2-target-priority`) — TextLayer avec nom et priorité.

## Recalcul automatique

`useAutoPlan` observe le tableau de cibles. Toute modification déclenche un debounce de 400 ms, puis un `POST /api/sites/{siteId}/plans`. La règle « dernière demande gagne » est appliquée via un compteur de séquence (`reqCounterRef`) et un `AbortController` qui annule la requête en vol précédente.

L'indicateur `computing` est vrai pendant toute la durée du calcul en cours ; `TargetsPanel` l'affiche comme un badge animé `role="status" aria-live="polite"`.

## Comparateur de variantes

Les trois variantes sont affichées à égalité dans des cartes distinctes. Aucune n'est sélectionnée automatiquement. Le choix de l'astronaute passe par `PATCH /api/plans/{id}` via `useSelectRoute`, qui met à jour `activeRouteId` dans le magasin partagé.

Chaque carte montre :
- Distance, durée totale, dose, oxygène, nombre de cibles
- Statut de retour (`✓`, `▲`, `⛔`) avec réserve en %
- Warnings de la variante (couche manquante, marge accrue)
- Explication par tronçon (dépliable) : « contourne une pente de 24° »
- Point de non-retour et cibles à couper si le retour n'est pas garanti

## Critères d'acceptation

| Critère | Comment il est démontré |
|---|---|
| Le tracé se met à jour après le déplacement d'une cible | `useAutoPlan` s'abonne aux changements de cibles et recalcule automatiquement ; test « debounce » vérifie un seul POST |
| Aucune variante n'est imposée | `RouteComparator` n'appelle jamais `setActiveRoute` automatiquement ; le test vérifie l'absence de badge « Choisie » à l'affichage initial |
| Chaque variante explique pourquoi elle passe là | `SegmentExplanations` affiche `route.explanation` par tronçon ; test comparateur vérifie la présence des trois cartes |

## Exigences couvertes

- **EF-04** : ajout, déplacement, suppression de cibles ; fiche d'objectif, de mesure et de temps de travail.
- **EF-05** : trois variantes d'itinéraire calculées et affichées ; choix de variante par l'astronaute.
- **ENF-12** : recalcul automatique après toute modification, avec indicateur de calcul.

## Demande de changement de contrat ouverte

`tasks/change-requests/F2-pickmode-map-click.md` : ajouter un mécanisme dans `MapView` et `store.ts` (gelés) pour transmettre les clics carte aux fonctionnalités en mode `addTarget`. Contournement actuel : couche deck.gl transparente couvrant la bbox du site.
