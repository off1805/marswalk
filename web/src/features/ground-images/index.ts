/**
 * Images au sol (G1, EF-09) : trajet de Perseverance et points de prise de vue sur la carte,
 * visionneuse, images les plus proches de la cible sélectionnée.
 * Règle : ne jamais importer le code d'une autre fonctionnalité ; passer par le magasin
 * partagé (@/shared/store) ou par l'API (@/shared/api/client).
 */
import type { Feature } from "@/app/feature";
import { ImageViewer } from "./ImageViewer";
import { groundImageLayers } from "./layers";
import { NearbyImages } from "./NearbyImages";

export const feature: Feature = {
  id: "ground-images",
  panels: [
    { slot: "map-overlay", order: 50, component: ImageViewer, modes: ["map"] },
    { slot: "right", order: 40, component: NearbyImages, modes: ["map"] },
  ],
  mapLayers: groundImageLayers,
  routes: [],
};
