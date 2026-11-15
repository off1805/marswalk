# F6 — Vue 3D

Terrain martien en relief, avec le tracé posé au sol et un survol caméra « à la poursuite » du
marcheur. Le rendu utilise MapLibre (même moteur que la carte 2D) : maillage de terrain,
ombrage du relief, ciel martien et brume à l'horizon.

## Fichiers

```
terrain3d/
├── terrain.config.ts    URLs des tuiles et décodeur terrain-RGB
├── demProtocol.ts       Protocole mwdem:// : tuiles d'altitude relatives au site
├── flyover.ts           Calculs purs d'animation (échantillonnage du profil, avance)
├── camera.ts            Caméra de poursuite, vues prédéfinies, échelle Mars / MapLibre
├── useTerrain3dData.ts  Manifeste + plan actif + cibles + altitude de référence
├── useFlyover.ts        État du survol (lecture, curseur, vitesse, exagération)
├── TerrainCanvas.tsx    Rendu MapLibre : relief, ombrage, ciel, tracé, cibles, marcheur
├── FlyoverControls.tsx  Barre de survol
├── Terrain3dView.tsx    Assemblage de la vue
├── terrain3d.test.ts    Tests des fonctions pures
└── index.ts             Route /3d, chargée à la demande
```

## Relief réaliste

- **Altitudes relatives.** Les tuiles terrain-RGB portent l'altitude absolue (≈ −2 600 m) et
  leurs pixels hors site sont transparents (décodés à −10 000 m). `demProtocol.ts` réécrit
  chaque tuile par rapport à l'altitude médiane du site (mesurée sur ses tuiles) et met les
  trous à cette référence. Les tuiles hors site sont plates, servies sans requête : la plaine
  continue au-delà du site, sans « socle » ni falaises de bord.
- **Exagération.** Elle s'applique au relief seul (×1 à ×10, ×2 par défaut).
- **Échelle.** MapLibre mesure le sol avec le rayon terrestre ; sur des degrés martiens ses
  mètres horizontaux sont 1,88 fois trop longs. Les hauteurs sont multipliées d'autant
  (`MARS_TO_RENDER`) : ×1 donne les vraies pentes.
- **Lecture du relief.** Ombrage multidirectionnel calculé sur le même MNT, voile d'oxyde de
  fer, ciel caramel et brume en fond de scène.

## Caméra

- Inclinaison jusqu'à 85° : on descend au niveau du sol et on regarde une pente en face.
- Vues : Overview (oblique 62°), Top (0°), Ground level (80°, à l'endroit courant).
- Survol : caméra 70 m derrière le marcheur, 28 m au-dessus du sol, visée 90 m plus loin.
  Prendre la main sur la caméra met le survol en pause ; le curseur permet de se placer
  n'importe où sur le tracé.

## Synchronisation

- `useFlyover` écrit `hoverDistanceM` dans le magasin partagé : le profil (F3) suit.
- Le plan et la variante choisie sont conservés au rechargement (`app/PlanSync.tsx`) : la vue
  3D ouverte directement retrouve le tracé.

## Critères d'acceptation

| Critère | Démonstration |
|---|---|
| Le survol se lance d'un clic | Bouton « Fly the route » |
| ≥ 30 images/s | Rendu WebGL MapLibre, `requestAnimationFrame` |
| Exagération réglable et indiquée | Sélecteur ×1…×10, valeur active mise en évidence |
| Repère synchronisé avec F3 | `useFlyover` → `setHoverDistance` → magasin partagé |
