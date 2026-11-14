import type { SlotName } from "./feature";
import { registry } from "./registry";
import { useShared } from "@/shared/store";

/** Affiche, dans l'ordre, les panneaux que les fonctionnalités placent dans un emplacement. */
export function Slot({ name, className = "" }: { name: SlotName; className?: string }) {
  const mode = useShared((s) => s.mode);
  const panels = registry
    .flatMap((f) => f.panels.map((p) => ({ ...p, featureId: f.id })))
    .filter((p) => p.slot === name && (!p.modes || p.modes.includes(mode)))
    .sort((a, b) => a.order - b.order);
  if (panels.length === 0) return null;
  return (
    <div data-slot={name} className={className}>
      {panels.map(({ component: Component, featureId, order }) => (
        <Component key={`${featureId}-${order}`} />
      ))}
    </div>
  );
}
