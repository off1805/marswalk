/**
 * Contrat d'une fonctionnalité du front (gelé avec contrats-v2, taches-agents.md §8).
 * Chaque fonctionnalité exporte `feature` depuis features/<nom>/index.ts.
 */
import type { Layer } from "@deck.gl/core";
import type { LayerSpecification, SourceSpecification } from "maplibre-gl";
import type { ComponentType } from "react";
import type { SiteManifest } from "@/shared/api/client";
import type { Mode, SharedState } from "@/shared/store";

/** Emplacements fixes de la coquille. */
export const SLOTS = [
  "left",
  "right",
  "bottom",
  "top-banner",
  "map-overlay",
] as const;
export type SlotName = (typeof SLOTS)[number];

export interface PanelSpec {
  slot: SlotName;
  /** Ordre croissant dans l'emplacement. */
  order: number;
  component: ComponentType;
  /** Modes où le panneau apparaît ; tous si absent. */
  modes?: Mode[];
}

/** Contexte passé aux fonctions qui produisent des couches de carte. */
export interface MapContext {
  siteId: string;
  manifest: SiteManifest;
  zoom: number;
  state: SharedState;
}

/** Une source MapLibre et ses couches de style, ajoutées sous les couches deck.gl. */
export interface MapSourceSpec {
  id: string;
  source: SourceSpecification;
  layers: LayerSpecification[];
}

export interface FeatureRoute {
  path: string;
  component: ComponentType;
}

export interface Feature {
  id: string;
  panels: PanelSpec[];
  /** Couches deck.gl, recalculées à chaque changement de contexte. */
  mapLayers?: (ctx: MapContext) => Layer[];
  /** Sources MapLibre, fixes ou dépendantes du contexte. */
  mapSources?: MapSourceSpec[] | ((ctx: MapContext) => MapSourceSpec[]);
  routes: FeatureRoute[];
  /** Appelé une fois au démarrage (par ex. service worker de F7). */
  setup?: () => void | Promise<void>;
}

/** Fonctionnalité vide, point de départ des modules créés par T00. */
export function emptyFeature(id: string): Feature {
  return { id, panels: [], routes: [] };
}
