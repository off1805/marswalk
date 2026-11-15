/** Mises en page de l'interface web : la carte et la vue 3D (taches-agents.md §8). */
import type { ReactNode } from "react";
import { Link } from "react-router";
import { MapView } from "./MapView";
import { registry } from "./registry";
import { SitePicker } from "./SitePicker";
import { Slot } from "./Slot";
import { useHealth, useMarsClock, useSiteManifest } from "@/shared/hooks";
import { applyTheme } from "@/shared/theme";

function TopBar() {
  const health = useHealth();
  const clock = useMarsClock();
  const site = useSiteManifest();
  const apiOk = health.isSuccess;
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2">
      <strong className="text-lg">Marswalk</strong>
      <span>{site.data?.name ?? "…"}</span>
      <SitePicker />
      {clock.data && (
        <span aria-label="Martian time">
          Sol {clock.data.sol} · {clock.data.lmst} LMST
        </span>
      )}
      <span aria-label="API status" className="text-sm text-[var(--text-muted)]">
        {apiOk ? "● API" : "○ API offline"}
      </span>
      <nav className="ml-auto flex gap-3" aria-label="Views">
        <Link to="/">Map</Link>
        <Link to="/3d">3D</Link>
      </nav>
      <span className="flex gap-1">
        <button type="button" onClick={() => applyTheme("day")} aria-label="Day theme">
          ☀
        </button>
        <button type="button" onClick={() => applyTheme("night")} aria-label="Night theme">
          ☾
        </button>
      </span>
    </header>
  );
}

function MapArea() {
  const site = useSiteManifest();
  if (site.isError) return <p className="p-4">Site unavailable: {String(site.error)}</p>;
  if (!site.data) return <p className="p-4">Loading site…</p>;
  return (
    <div className="relative h-full w-full">
      <MapView manifest={site.data} />
      <Slot name="map-overlay" className="pointer-events-none absolute inset-0 [&>*]:pointer-events-auto" />
    </div>
  );
}

function Frame({ mode, children }: { mode: string; children: ReactNode }) {
  return (
    <div data-mode={mode} className="flex h-full flex-col">
      {children}
    </div>
  );
}

/** Interface web : carte au centre, panneaux latéraux et panneau du bas. */
export function MapLayout() {
  return (
    <Frame mode="map">
      <TopBar />
      <Slot name="top-banner" />
      <div className="flex min-h-0 flex-1">
        <Slot name="left" className="flex w-80 flex-col gap-2 overflow-y-auto p-2" />
        <main className="min-w-0 flex-1">
          <MapArea />
        </main>
        <Slot name="right" className="flex w-96 flex-col gap-2 overflow-y-auto p-2" />
      </div>
      <Slot name="bottom" className="h-56 border-t border-[var(--border)]" />
    </Frame>
  );
}

/** 3D view: rendered by the /3d route of a feature (F6), otherwise a placeholder. */
export function Terrain3dLayout() {
  const route = registry.flatMap((f) => f.routes).find((r) => r.path === "/3d");
  return (
    <Frame mode="3d">
      <TopBar />
      <div className="min-h-0 flex-1">{route ? <route.component /> : <p className="p-4">3D view coming soon (F6).</p>}</div>
    </Frame>
  );
}
