# Demande de changement F2 : mécanisme de clic carte pour `pickMode = addTarget`

**Date :** 2026-11-14  
**Tâche :** F2 — Cibles et itinéraire  
**Sujet :** Transmission des clics carte aux fonctionnalités en mode `pickMode`

## Problème

Le contrat `Feature` (gelé) ne prévoit aucun mécanisme pour qu'une fonctionnalité reçoive les coordonnées d'un clic carte quand `pickMode = addTarget`. Le `MapView` crée la carte MapLibre et gère les couches deck.gl, mais il n'expose ni callback ni événement partagé.

## Comportement voulu

Quand `pickMode = "addTarget"`, un clic sur la carte devrait déclencher l'ajout d'une cible aux coordonnées cliquées. F2 a besoin de ces coordonnées `[lon, lat]` en degrés (règle R2).

## Champ concerné

- `web/src/app/MapView.tsx` (T00, gelé) : ajouter un gestionnaire `onClick` conditionnel lorsque `pickMode !== "none"` qui écrit les coordonnées dans le magasin partagé.
- `web/src/shared/store.ts` (T00, gelé) : ajouter un champ `lastPickedCoords: LonLat | null` et son setter `setLastPickedCoords`.

## Effet sur les autres tâches

- F3 (profil) et F4 (sécurité) ne lisent pas `lastPickedCoords` : aucun effet.
- F1 (carte) écoute `pickMode` pour le mode interrogation ; il peut lire `lastPickedCoords` si nécessaire.

## Contournement retenu dans F2

En attendant l'application de cette demande, F2 utilise une couche deck.gl `ScatterplotLayer` sur la zone entière avec `onClick` activé et `pickable: true`. Quand `pickMode = "addTarget"`, deck.gl capture le clic et passe `info.coordinate` (longitude, latitude) à un callback interne de F2. Ce contournement fonctionne dans les deux cas (mode mock et mode complet) car deck.gl gère les clics de manière indépendante de MapLibre.

**Limitation :** si deck.gl passe la main à MapLibre avant que F2 ne capte le clic (par exemple clic hors emprise de la couche), la position ne sera pas captée. Dans la pratique la couche couvre toute la bbox du site, donc le contournement est complet.
