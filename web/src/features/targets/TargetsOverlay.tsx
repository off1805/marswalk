/**
 * Overlay de la fonctionnalité F2 dans le slot `map-overlay`.
 * Affiche la légende des zones et un tooltip de survol.
 * Utilise useTargetLayers pour partager l'état de survol.
 */
import { HazardsOverlay } from "./HazardOverlay";
import { targetsStore } from "./targetsStore";

export function TargetsOverlay() {
  const hazardHover = targetsStore((s) => s.hazardHoverText);
  return <HazardsOverlay hazardHover={hazardHover} />;
}
