import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import { api, type DisplayPreset, type SiteManifest } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared, type LayerView } from "@/shared/store";

export function usePresets(manifest?: SiteManifest) {
  const currentPreset = useShared((s) => s.preset);
  const setPreset = useShared((s) => s.setPreset);
  const setLayers = useShared((s) => s.setLayers);

  const presetsQuery = useQuery({
    queryKey: queryKeys.presets(),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/presets");
      if (error || !data) throw new Error("Failed to load presets");
      return data as DisplayPreset[];
    },
    staleTime: Infinity,
  });

  const applyPreset = useCallback(
    (presetId: string) => {
      const preset = presetsQuery.data?.find((p) => p.id === presetId);
      if (!preset) return;

      setPreset(presetId);

      // Construction du nouvel état des couches en préservant toutes les couches du manifeste
      const currentLayers = useShared.getState().layers;
      const updatedLayers: Record<string, LayerView> = {};

      if (manifest) {
        for (const layer of manifest.layers) {
          const presetView = preset.layers[layer.id];
          if (presetView) {
            updatedLayers[layer.id] = {
              visible: presetView.visible,
              opacity: presetView.opacity ?? 1.0,
            };
          } else {
            updatedLayers[layer.id] = {
              visible: false,
              opacity: currentLayers[layer.id]?.opacity ?? 1.0,
            };
          }
        }
      } else {
        for (const [id, view] of Object.entries(preset.layers)) {
          updatedLayers[id] = { visible: view.visible, opacity: view.opacity ?? 1.0 };
        }
      }

      setLayers(updatedLayers);
    },
    [presetsQuery.data, manifest, setPreset, setLayers]
  );

  // Initialisation par défaut si aucune couche n'est encore configurée
  useEffect(() => {
    if (
      presetsQuery.data &&
      manifest &&
      Object.keys(useShared.getState().layers).length === 0
    ) {
      const initialPresetId = manifest.default_preset || "safety";
      applyPreset(initialPresetId);
    }
  }, [presetsQuery.data, manifest, applyPreset]);

  return {
    presets: presetsQuery.data ?? [],
    currentPreset,
    applyPreset,
    isLoading: presetsQuery.isLoading,
  };
}
