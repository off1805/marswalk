import { useMemo } from "react";
import { Panel } from "@/shared/ui/Panel";
import { useSiteManifest } from "@/shared/hooks";
import { useShared } from "@/shared/store";
import { LayerRow } from "./LayerRow";
import { usePresets } from "../hooks/usePresets";
import type { LayerKind, LayerKindGroup } from "../types";

const KIND_TITLES: Record<LayerKind, string> = {
  imagery: "Imagerie de surface",
  dem: "Modèles numériques de terrain",
  derived: "Couches dérivées & Risques",
  thermal: "Inertie thermique",
  spectral: "Minéralogie & Spectrométrie",
  vector: "Vecteurs & Traverses",
  ground: "Observations au sol",
};

const KIND_ORDER: LayerKind[] = [
  "derived",
  "imagery",
  "dem",
  "thermal",
  "spectral",
  "vector",
  "ground",
];

export function LayerPanel() {
  const { data: manifest, isLoading } = useSiteManifest();
  const layersState = useShared((s) => s.layers);
  const setLayer = useShared((s) => s.setLayer);
  const { presets, currentPreset, applyPreset } = usePresets(manifest);

  // Regroupement des couches par catégorie
  const groups: LayerKindGroup[] = useMemo(() => {
    if (!manifest) return [];
    const grouped = new Map<LayerKind, typeof manifest.layers>();

    for (const layer of manifest.layers) {
      const list = grouped.get(layer.kind) ?? [];
      list.push(layer);
      grouped.set(layer.kind, list);
    }

    return KIND_ORDER.filter((k) => grouped.has(k)).map((kind) => ({
      kind,
      title: KIND_TITLES[kind] ?? kind,
      layers: grouped.get(kind)!,
    }));
  }, [manifest]);

  if (isLoading || !manifest) {
    return (
      <Panel title="Couches cartographiques">
        <p className="text-xs text-[var(--text-muted)] animate-pulse">
          Chargement des couches du site…
        </p>
      </Panel>
    );
  }

  return (
    <Panel title="Couches cartographiques">
      {/* Sélecteur de préréglages */}
      <div className="mb-3">
        <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
          Préréglages d'affichage
        </label>
        <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Préréglages">
          {presets.map((p) => {
            const isActive = currentPreset === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => applyPreset(p.id)}
                className={`flex-1 rounded px-2 py-1 text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-[var(--color-info)] text-white shadow-sm"
                    : "bg-[var(--surface-2)] text-[var(--text-muted)] hover:text-[var(--text)] border border-[var(--border)]"
                }`}
                role="radio"
                aria-checked={isActive}
              >
                {p.title}
              </button>
            );
          })}
        </div>
      </div>

      {/* Groupes de couches */}
      <div className="flex flex-col gap-3">
        {groups.map((group) => (
          <div key={group.kind} className="space-y-1.5">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {group.title}
            </h3>
            <div className="space-y-1">
              {group.layers.map((layer) => {
                const view = layersState[layer.id] ?? {
                  visible: false,
                  opacity: 1.0,
                };
                return (
                  <LayerRow
                    key={layer.id}
                    layer={layer}
                    view={view}
                    onToggleVisibility={(visible) => setLayer(layer.id, { visible })}
                    onChangeOpacity={(opacity) => setLayer(layer.id, { opacity })}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
