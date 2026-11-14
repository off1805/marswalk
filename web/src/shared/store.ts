/**
 * Magasin partagé (Zustand), gelé avec contrats-v2 (taches-agents.md §8).
 * Toute modification passe par tasks/change-requests/.
 *
 * L'état d'interface partagé entre fonctionnalités vit ici ; les données serveur passent
 * par TanStack Query (shared/queryKeys.ts).
 */
import { create } from "zustand";

/** Vue courante de l'interface web : la carte (`/`) ou la vue 3D (`/3d`). */
export type Mode = "map" | "3d";
export type PickMode = "none" | "query" | "addTarget";

export interface LayerView {
  visible: boolean;
  opacity: number;
}

export interface SharedState {
  siteId: string;
  mode: Mode;
  /** Visibilité et opacité par identifiant de couche. */
  layers: Record<string, LayerView>;
  /** Préréglage d'affichage courant (config/presets.yaml). */
  preset: string;
  selectedTargetId: string | null;
  activePlanId: string | null;
  activeRouteId: string | null;
  /** Distance cumulée survolée le long de l'itinéraire actif ; synchronise carte, profil et 3D. */
  hoverDistanceM: number | null;
  evaId: string | null;
  pickMode: PickMode;

  setSiteId: (siteId: string) => void;
  setMode: (mode: Mode) => void;
  setLayer: (layerId: string, view: Partial<LayerView>) => void;
  setLayers: (layers: Record<string, LayerView>) => void;
  setPreset: (preset: string) => void;
  selectTarget: (targetId: string | null) => void;
  setActivePlan: (planId: string | null) => void;
  setActiveRoute: (routeId: string | null) => void;
  setHoverDistance: (distanceM: number | null) => void;
  setEvaId: (evaId: string | null) => void;
  setPickMode: (pickMode: PickMode) => void;
}

export const DEFAULT_SITE_ID = "fictif";

export const useShared = create<SharedState>()((set) => ({
  siteId: DEFAULT_SITE_ID,
  mode: "map",
  layers: {},
  preset: "safety",
  selectedTargetId: null,
  activePlanId: null,
  activeRouteId: null,
  hoverDistanceM: null,
  evaId: null,
  pickMode: "none",

  setSiteId: (siteId) => set({ siteId }),
  setMode: (mode) => set({ mode }),
  setLayer: (layerId, view) =>
    set((s) => ({
      layers: {
        ...s.layers,
        [layerId]: { visible: false, opacity: 1, ...s.layers[layerId], ...view },
      },
    })),
  setLayers: (layers) => set({ layers }),
  setPreset: (preset) => set({ preset }),
  selectTarget: (selectedTargetId) => set({ selectedTargetId }),
  setActivePlan: (activePlanId) => set({ activePlanId }),
  setActiveRoute: (activeRouteId) => set({ activeRouteId }),
  setHoverDistance: (hoverDistanceM) => set({ hoverDistanceM }),
  setEvaId: (evaId) => set({ evaId }),
  setPickMode: (pickMode) => set({ pickMode }),
}));
