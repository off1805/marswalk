# F6 — Vue 3D

Rendu immersif du terrain martien avec survol automatique de l'itinéraire.

## Architecture (principes SOLID)

Chaque fichier a une responsabilité unique et dépend d'abstractions, pas d'implémentations.

```
terrain3d/
├── terrain.config.ts    Configuration du décodage altitude (injectable)
├── flyover.ts           Calculs purs de caméra et d'animation (sans React)
├── routeLayer.ts        Construction de la PathLayer deck.gl de l'itinéraire
├── useTerrain3dData.ts  Hook de données : manifeste + plan actif → abstractions
├── useFlyover.ts        Hook React : état de l'animation + synchronisation F3
├── TerrainCanvas.tsx    Rendu deck.gl (reçoit des abstractions, pas des stores)
├── FlyoverControls.tsx  Contrôles UI lecture/pause/vitesse/exagération
├── Terrain3dView.tsx    Assembleur : compose les pièces, ne calcule rien
├── terrain3d.test.ts    Tests unitaires des fonctions pures
└── index.ts             Export de la feature (route /3d)
```

### Principe S — Single Responsibility

| Fichier | Raison de changer |
|---|---|
| `terrain.config.ts` | Format d'encodage des tuiles altitude |
| `flyover.ts` | Algorithme de caméra ou constantes d'animation |
| `routeLayer.ts` | Style visuel du tracé sur le terrain |
| `useTerrain3dData.ts` | Sources de données ou transformation de format |
| `useFlyover.ts` | Interaction React (timers, effets) |
| `TerrainCanvas.tsx` | Paramètres du rendu deck.gl |
| `FlyoverControls.tsx` | Ergonomie des contrôles UI |
| `Terrain3dView.tsx` | Assemblage des pièces |

### Principe O — Open/Closed

`ElevationDecoder` est un objet de configuration injecté dans `TerrainConfig`. Ajouter le support d'un nouveau format terrain (par exemple l'encodage Mapzen) ne modifie pas `TerrainCanvas` : on crée un nouveau décodeur et on le passe en prop.

### Principe D — Dependency Inversion

`TerrainCanvas` dépend de `TerrainConfig` et `CameraTarget` (abstractions définies dans le module), pas de `SiteManifest` ni de `QueryClient`. `Terrain3dView` injecte les dépendances concrètes depuis ses hooks.

## Flux de données

```
SiteManifest ──► useTerrain3dData ──► TerrainConfig ──► TerrainCanvas
Plan/Route   ──►                 ──► RouteProfile  ──► useFlyover ──► CameraTarget
                                 ──► Route         ──► buildRouteLayer
```

## Synchronisation avec F3 (profil)

`useFlyover` écrit `hoverDistanceM` dans le magasin partagé (Zustand) à chaque tick d'animation. F3 (profil d'altitude) lit cette valeur pour déplacer son repère en temps réel — sans aucun couplage direct entre F6 et F3.

## Exagération verticale

L'exagération est appliquée en multipliant les scalers RGB du décodeur d'élévation par le facteur choisi. Les valeurs disponibles sont ×1, ×2, ×3, ×5, ×10. La valeur courante est toujours affichée à l'écran.

## Critères d'acceptation

| Critère | Démonstration |
|---|---|
| Le survol se lance d'un clic | Bouton ▶ Survol dans `FlyoverControls` |
| ≥ 30 images/s | deck.gl utilise WebGL2 avec `requestAnimationFrame` natif |
| Exagération réglable et indiquée | Boutons ×1…×10, label `aria-live` |
| Repère synchronisé avec F3 | `useFlyover` → `setHoverDistance` → magasin partagé |
