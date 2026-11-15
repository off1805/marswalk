/**
 * Magasin interne de F2 (non partagé).
 * Stocke l'état d'interaction des couches de carte (hover de zone, drag) pour
 * que l'overlay et la couche puissent communiquer sans passer par props.
 */
import { create } from "zustand";

interface TargetsState {
  hazardHoverText: string | null;
  draggingTargetId: string | null;
  /** Last failed target action, shown in the targets panel. */
  actionError: string | null;
  setHazardHoverText: (text: string | null) => void;
  setDraggingTargetId: (id: string | null) => void;
  setActionError: (msg: string | null) => void;
}

export const targetsStore = create<TargetsState>()((set) => ({
  hazardHoverText: null,
  draggingTargetId: null,
  actionError: null,
  setHazardHoverText: (hazardHoverText) => set({ hazardHoverText }),
  setDraggingTargetId: (draggingTargetId) => set({ draggingTargetId }),
  setActionError: (actionError) => set({ actionError }),
}));
