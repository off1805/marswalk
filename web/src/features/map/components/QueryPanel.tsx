import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/shared/ui/Panel";
import { Button } from "@/shared/ui/Button";
import { AlertBadge } from "@/shared/ui/AlertBadge";
import { api, type PointQuery } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";
import { useSiteManifest } from "@/shared/hooks";
import { onMapClick } from "@/shared/mapClick";
import type { PointValue } from "../types";

function PointValueItem({ value }: { value: PointValue }) {
  const isMissing = value.status === "missing";
  const isDegraded = value.status === "degraded";

  const displayVal = value.value !== null && value.value !== undefined
    ? `${Number.isInteger(value.value) ? value.value : value.value.toFixed(2)}${value.unit ? ` ${value.unit}` : ""}`
    : "—";

  return (
    <div className="flex items-start justify-between border-b border-[var(--border)] py-1.5 text-xs last:border-b-0">
      <div className="min-w-0 pr-2">
        <div className="font-semibold text-[var(--text)] truncate" title={value.title}>
          {value.title}
        </div>
        <div className="text-[10px] text-[var(--text-muted)]">
          {value.source.instrument}
          {value.uncertainty?.coreg_m !== null && value.uncertainty?.coreg_m !== undefined && (
            <span> · Recalage ±{value.uncertainty?.coreg_m}m</span>
          )}
        </div>
      </div>

      <div className="text-right flex flex-col items-end shrink-0">
        <span className="font-mono font-medium text-[var(--text)]">
          {value.label ? `${value.label} (${displayVal})` : displayVal}
        </span>
        {isDegraded && <AlertBadge level="caution" text="Dégradé" />}
        {isMissing && <span className="text-[10px] text-[var(--text-muted)] italic">Non mesuré</span>}
      </div>
    </div>
  );
}

export function QueryPanel() {
  const siteId = useShared((s) => s.siteId);
  const pickMode = useShared((s) => s.pickMode);
  const setPickMode = useShared((s) => s.setPickMode);

  const habitat = useSiteManifest().data?.habitat;

  // Coordonnées interrogées : l'habitat du site tant qu'aucun point n'a été choisi.
  const [picked, setPicked] = useState<{ siteId: string; lon: number; lat: number } | null>(null);
  const coords =
    picked && picked.siteId === siteId
      ? picked
      : habitat
        ? { lon: habitat[0], lat: habitat[1] }
        : null;
  const setCoords = (next: { lon: number; lat: number }) => setPicked({ siteId, ...next });

  const isQueryMode = pickMode === "query";

  // Un clic sur la carte en mode interrogation interroge ce point (écart E1).
  useEffect(() => {
    if (!isQueryMode) return;
    return onMapClick(({ lon, lat }) => setPicked({ siteId, lon, lat }));
  }, [isQueryMode, siteId]);

  const { data: queryResult, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.query(siteId, coords?.lon ?? NaN, coords?.lat ?? NaN),
    queryFn: async () => {
      if (!coords) throw new Error("Site en cours de chargement");
      const { data, error } = await api.GET("/api/sites/{site_id}/query", {
        params: {
          path: { site_id: siteId },
          query: { lon: coords.lon, lat: coords.lat },
        },
      });
      if (error || !data) throw new Error("Erreur lors de l'interrogation du point");
      return data as PointQuery;
    },
    enabled: isQueryMode && coords !== null,
    staleTime: 5000,
  });

  return (
    <Panel title="Interrogation au sol (EF-07)">
      {/* Contrôle du mode interrogation */}
      <div className="mb-3 space-y-2">
        <div className="flex items-center gap-2">
          <Button
            variant={isQueryMode ? "primary" : "secondary"}
            onClick={() => setPickMode(isQueryMode ? "none" : "query")}
            className="w-full text-xs"
          >
            {isQueryMode ? "● Mode interrogation actif" : "Activer l'interrogation"}
          </Button>
        </div>

        {isQueryMode && (
          <div className="rounded bg-[var(--surface-2)] p-2 text-[11px] text-[var(--text-muted)]">
            <div className="mb-1">Cliquez sur la carte ou saisissez une coordonnée :</div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] font-mono">Lon (°E)</label>
                <input
                  type="number"
                  step="0.001"
                  value={coords?.lon ?? ""}
                  onChange={(e) => coords && setCoords({ ...coords, lon: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 font-mono text-xs text-[var(--text)]"
                />
              </div>
              <div>
                <label className="text-[10px] font-mono">Lat (°N)</label>
                <input
                  type="number"
                  step="0.001"
                  value={coords?.lat ?? ""}
                  onChange={(e) => coords && setCoords({ ...coords, lat: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 font-mono text-xs text-[var(--text)]"
                />
              </div>
            </div>
            <button
              type="button"
              onClick={() => refetch()}
              className="mt-2 w-full rounded bg-[var(--surface)] py-1 text-[11px] font-semibold text-[var(--color-info)] hover:underline"
            >
              Interroger ce point
            </button>
          </div>
        )}
      </div>

      {/* Résultats de l'interrogation */}
      {isQueryMode && (
        <div>
          {isLoading && (
            <p className="text-xs text-[var(--text-muted)] animate-pulse">
              Échantillonnage de toutes les couches…
            </p>
          )}

          {error && (
            <p className="text-xs text-[var(--color-danger)]">
              {error instanceof Error ? error.message : "Erreur d'interrogation"}
            </p>
          )}

          {queryResult && (
            <div className="space-y-3">
              {/* Synthèse retour à l'habitat */}
              {typeof queryResult.return_time_s === "number" && (
                <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-2">
                  <div className="text-[10px] uppercase font-bold text-[var(--text-muted)]">
                    Temps de retour estimé
                  </div>
                  <div className="text-sm font-bold font-mono text-[var(--color-ok)]">
                    {Math.round(queryResult.return_time_s / 60)} min ({queryResult.return_time_s} s)
                  </div>
                </div>
              )}

              {/* Valeurs des couches */}
              <div>
                <div className="mb-1 text-[10px] uppercase font-bold text-[var(--text-muted)]">
                  Valeurs des couches ({queryResult.values.length})
                </div>
                <div className="max-h-72 overflow-y-auto pr-1">
                  {queryResult.values.map((v) => (
                    <PointValueItem key={v.layer_id} value={v} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
