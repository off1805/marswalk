/**
 * Console layout state (shell only). Kept apart from shared/store.ts, which is a frozen
 * contract between features. Remembered per browser; storage may be unavailable.
 */
import { create } from "zustand";

const KEY = "marswalk.console.v1";

interface Persisted {
  /** Open tool section in the rail, or null when the drawer is closed. */
  section: string | null;
  /** EVA safety pane folded down to its header. */
  evaCollapsed: boolean;
  /** Elevation profile sheet unfolded. */
  profileOpen: boolean;
}

export interface ConsoleState extends Persisted {
  tourOpen: boolean;
  setSection: (id: string | null) => void;
  toggleSection: (id: string) => void;
  setEvaCollapsed: (v: boolean) => void;
  setProfileOpen: (v: boolean) => void;
  setTourOpen: (v: boolean) => void;
}

const DEFAULTS: Persisted = {
  // On a phone the map comes first; on larger screens the planning tool starts open.
  section: typeof window !== "undefined" && window.innerWidth < 768 ? null : "targets",
  evaCollapsed: false,
  profileOpen: false,
};

function load(): Persisted {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    /* storage unavailable: defaults apply */
  }
  return DEFAULTS;
}

function save(s: Persisted) {
  try {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({ section: s.section, evaCollapsed: s.evaCollapsed, profileOpen: s.profileOpen }),
    );
  } catch {
    /* storage unavailable */
  }
}

export const useConsole = create<ConsoleState>()((set, get) => {
  const commit = (patch: Partial<ConsoleState>) => {
    set(patch);
    save(get());
  };
  return {
    ...load(),
    tourOpen: false,
    setSection: (section) => commit({ section }),
    toggleSection: (id) => commit({ section: get().section === id ? null : id }),
    setEvaCollapsed: (evaCollapsed) => commit({ evaCollapsed }),
    setProfileOpen: (profileOpen) => commit({ profileOpen }),
    setTourOpen: (tourOpen) => set({ tourOpen }),
  };
});

const TOUR_KEY = "marswalk.tour.v1";

export function tourSeen(): boolean {
  try {
    return window.localStorage.getItem(TOUR_KEY) === "done";
  } catch {
    return true;
  }
}

export function markTourSeen() {
  try {
    window.localStorage.setItem(TOUR_KEY, "done");
  } catch {
    /* storage unavailable */
  }
}
