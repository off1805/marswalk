/**
 * Clics sur la carte, diffusés aux fonctionnalités (écart E1).
 *
 * La coquille (MapView) émet chaque clic de la carte, avec ses coordonnées en degrés
 * (règle R2) ; une fonctionnalité s'abonne et filtre selon `pickMode`. Le clic est lu sur
 * MapLibre, donc il arrive même quand une couche deck.gl pickable se trouve sous le pointeur.
 * Contournement de la demande tasks/change-requests/F2-pickmode-map-click.md, sans toucher
 * au magasin partagé gelé.
 */
export interface MapClick {
  lon: number;
  lat: number;
}

type Listener = (click: MapClick) => void;
const listeners = new Set<Listener>();

export function emitMapClick(click: MapClick): void {
  for (const l of [...listeners]) l(click);
}

/** S'abonne aux clics de la carte ; renvoie la fonction de désabonnement. */
export function onMapClick(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
