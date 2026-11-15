/**
 * 3D view (F6), route `/3d`: the terrain edge to edge, a route chip, view and relief
 * options, and the flyover bar.
 *
 * This component only assembles: data from `useTerrain3dData`, animation state from
 * `useFlyover`, rendering in `TerrainCanvas`.
 */
import { useCallback, useState } from "react";
import { Link } from "react-router";
import { colors } from "@/shared/theme";
import type { ViewPreset } from "./camera";
import { EXAGGERATION_STEPS } from "./flyover";
import { FlyoverControls, Segmented } from "./FlyoverControls";
import { TerrainCanvas } from "./TerrainCanvas";
import { useFlyover } from "./useFlyover";
import { useTerrain3dData } from "./useTerrain3dData";

const VARIANT_LABEL: Record<string, string> = { safest: "Safest", fastest: "Fastest", science: "Science" };

const VIEWS: { id: ViewPreset; label: string; hint: string }[] = [
  { id: "overview", label: "Overview", hint: "Oblique view of the whole site" },
  { id: "top", label: "Top", hint: "Straight down, like the map" },
  { id: "ground", label: "Ground level", hint: "Tilt down to the surface where you are" },
];

function Centered({ children }: { children: string }) {
  return (
    <div className="absolute inset-0 grid place-items-center bg-[var(--bg)]">
      <p className="label-caps animate-pulse">{children}</p>
    </div>
  );
}

export function Terrain3dView() {
  const data = useTerrain3dData();
  const { terrainConfig, activeProfile, activeRoute, totalDistanceM, isLoading } = data;
  const flyover = useFlyover(activeProfile, totalDistanceM);
  const [preset, setPreset] = useState<{ name: ViewPreset } | null>(null);
  // Options open by default where there is room for them beside the terrain.
  const [optionsOpen, setOptionsOpen] = useState(() => typeof window === "undefined" || window.innerWidth >= 1024);
  const { playing, pause } = flyover;

  // Grabbing the camera during the flyover hands control back to the user.
  const handleUserMove = useCallback(() => {
    if (playing) pause();
  }, [playing, pause]);

  if (isLoading) return <Centered>Loading 3D terrain…</Centered>;
  if (!terrainConfig) return <Centered>Site manifest unavailable</Centered>;

  const variantColor = activeRoute ? colors.route[activeRoute.variant] : undefined;

  return (
    <div className="absolute inset-0 overflow-hidden" aria-label="3D terrain view">
      <TerrainCanvas
        config={terrainConfig}
        referenceM={data.referenceM}
        zoomRange={data.zoomRange}
        exaggeration={flyover.exaggeration}
        activeRoute={activeRoute}
        targets={data.targets}
        traverse={data.traverse}
        photos={data.photos}
        profile={activeProfile}
        progressM={flyover.progressM}
        following={flyover.playing}
        preset={preset}
        onUserMove={handleUserMove}
      />

      {/* Route */}
      <div className="pane absolute left-3 top-[68px] z-10 max-w-[min(22rem,calc(100%-1.5rem))] px-3.5 py-2.5 sm:left-4">
        {activeRoute ? (
          <p className="flex items-center gap-2 text-sm">
            <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: variantColor }} />
            <span className="font-medium">{VARIANT_LABEL[activeRoute.variant] ?? activeRoute.variant} route</span>
            <span className="font-mono text-xs tabular-nums text-[var(--text-muted)]">
              {(activeRoute.totals.distance_m / 1000).toFixed(2)} km
            </span>
          </p>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">
            No route yet.{" "}
            <Link to="/" className="text-[var(--text)] underline">
              Plan one on the map
            </Link>{" "}
            to fly it here.
          </p>
        )}
      </div>

      {/* View and relief */}
      <aside
        aria-label="3D view options"
        className="pane absolute right-3 top-[120px] z-10 flex w-[15.5rem] flex-col overflow-hidden sm:right-4 sm:top-[68px]"
      >
        <button
          type="button"
          onClick={() => setOptionsOpen((o) => !o)}
          aria-expanded={optionsOpen}
          className="flex h-10 items-center justify-between px-3 text-left text-[13px] font-medium hover:bg-[var(--surface-2)]"
        >
          View &amp; relief
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            aria-hidden="true"
            className={`text-[var(--text-muted)] transition-transform duration-300 ${optionsOpen ? "-rotate-90" : "rotate-90"}`}
          >
            <path d="m9 6 6 6-6 6" />
          </svg>
        </button>
        <div hidden={!optionsOpen} className="flex flex-col gap-3 border-t border-[var(--border)] p-3">
        <div>
          <p className="label-caps mb-1.5">View</p>
          <div className="flex flex-col gap-1">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => {
                  pause();
                  setPreset({ name: v.id });
                }}
                title={v.hint}
                aria-label={`${v.label} view`}
                className="flex h-8 items-center justify-between rounded-lg border border-[var(--border)] px-2.5 text-left text-[13px] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]"
              >
                {v.label}
                <span className="text-[11px] text-[var(--text-faint)]">{v.id === "ground" ? "85°" : v.id === "top" ? "0°" : "62°"}</span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="label-caps mb-1.5">Relief exaggeration</p>
          <Segmented
            label="Vertical exaggeration"
            options={EXAGGERATION_STEPS}
            value={flyover.exaggeration}
            onChange={flyover.setExaggeration}
            format={(e) => `×${e}`}
          />
        </div>
        <details className="text-xs text-[var(--text-muted)]">
          <summary className="cursor-pointer select-none text-[var(--text)]">Moving around</summary>
          <ul className="mt-1.5 space-y-1 leading-snug">
            <li>Drag: move across the terrain</li>
            <li>Right-drag or Ctrl + drag: tilt and turn</li>
            <li>Scroll or pinch: zoom in, down to the ground</li>
            <li>Shift + arrows: tilt and turn with the keyboard</li>
          </ul>
        </details>
        </div>
      </aside>

      {/* Flyover */}
      <div className="absolute inset-x-3 bottom-3 z-10 mx-auto max-w-[52rem] sm:bottom-4">
        <FlyoverControls
          playing={flyover.playing}
          progressM={flyover.progressM}
          totalDistanceM={totalDistanceM}
          speed={flyover.speed}
          onPlay={flyover.play}
          onPause={flyover.pause}
          onRewind={flyover.rewind}
          onSeek={flyover.seek}
          onSpeedChange={flyover.setSpeed}
        />
      </div>
    </div>
  );
}
