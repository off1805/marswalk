/**
 * The console's tool sections. Features place panels in the "left" and "right" slots
 * (feature.ts, frozen); the shell groups them into sections shown one at a time, in the
 * order of the walk-planning workflow. A panel no section claims lands in "More", so a
 * new feature is never lost.
 */
import type { ComponentType } from "react";
import type { IconName } from "./icons";
import { registry } from "./registry";
import type { Mode } from "@/shared/store";

export interface DockPanel {
  key: string;
  component: ComponentType;
}

export interface Section {
  id: string;
  title: string;
  /** One line under the title: what this section is for. */
  hint: string;
  icon: IconName;
  panels: DockPanel[];
}

interface SectionDef {
  id: string;
  title: string;
  hint: string;
  icon: IconName;
  claims: string[];
}

/** Pinned on the right on wide screens: the EVA safety pane. */
export const EVA_CLAIMS = ["safety:right:5"];

const SECTIONS: SectionDef[] = [
  { id: "layers", title: "Layers", hint: "Imagery, terrain hazards and display presets", icon: "layers", claims: ["map:left:10"] },
  { id: "science", title: "Science", hint: "Why this site, and what is worth sampling", icon: "science", claims: ["targets:left:20"] },
  { id: "targets", title: "Targets & route", hint: "Pick stops, then compare route variants", icon: "route", claims: ["targets:right:20"] },
  { id: "inspect", title: "Inspect", hint: "Query the ground and browse surface images", icon: "crosshair", claims: ["map:right:10", "ground-images:right:40"] },
  { id: "environment", title: "Environment", hint: "Live conditions and alert thresholds", icon: "gauge", claims: ["safety:right:30", "safety:right:35"] },
  { id: "field", title: "Field log", hint: "Report obstacles and notes during the walk", icon: "notebook", claims: ["offline:right:6"] },
  { id: "export", title: "Export", hint: "Printable plan and logbook", icon: "export", claims: ["export:right:90"] },
];

function panelsFor(mode: Mode) {
  return registry
    .flatMap((f) =>
      f.panels.map((p) => ({ ...p, key: `${f.id}:${p.slot}:${p.order}` })),
    )
    .filter((p) => (p.slot === "left" || p.slot === "right") && (!p.modes || p.modes.includes(mode)))
    .sort((a, b) => a.order - b.order);
}

/** Sections for a mode. `includeEva` adds the safety pane as a section (narrow screens). */
export function buildSections(mode: Mode, includeEva: boolean): { sections: Section[]; eva: DockPanel[] } {
  const all = panelsFor(mode);
  const byKey = new Map(all.map((p) => [p.key, p]));
  const claimed = new Set<string>([...EVA_CLAIMS, ...SECTIONS.flatMap((s) => s.claims)]);
  const pick = (claims: string[]): DockPanel[] =>
    claims.flatMap((k) => {
      const p = byKey.get(k);
      return p ? [{ key: p.key, component: p.component }] : [];
    });

  const eva = pick(EVA_CLAIMS);
  const sections: Section[] = [];
  if (includeEva && eva.length) {
    sections.push({ id: "eva", title: "EVA safety", hint: "Point of no return, reserves and dose", icon: "shield", panels: eva });
  }
  for (const def of SECTIONS) {
    const panels = pick(def.claims);
    if (panels.length) sections.push({ id: def.id, title: def.title, hint: def.hint, icon: def.icon, panels });
  }
  const rest = all.filter((p) => !claimed.has(p.key)).map((p) => ({ key: p.key, component: p.component }));
  if (rest.length) sections.push({ id: "more", title: "More", hint: "Other tools", icon: "more", panels: rest });
  return { sections, eva };
}
