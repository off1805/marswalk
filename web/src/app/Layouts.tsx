/** Les trois mises en page de la coquille, plus la vue 3D (taches-agents.md §8). */
import type { ReactNode } from "react";
import { Link } from "react-router";
import { MapView } from "./MapView";
import { registry } from "./registry";
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
      {clock.data && (
        <span aria-label="Heure martienne">
          Sol {clock.data.sol} · {clock.data.lmst} LMST
        </span>
      )}
      <span aria-label="État de l'API" className="text-sm text-[var(--text-muted)]">
        {apiOk ? "● API" : "○ API hors ligne"}
      </span>
      <nav className="ml-auto flex gap-3" aria-label="Modes">
        <Link to="/">Habitat</Link>
        <Link to="/tablet">Tablette</Link>
        <Link to="/hud">HUD</Link>
        <Link to="/3d">3D</Link>
      </nav>
      <span className="flex gap-1">
        <button type="button" onClick={() => applyTheme("day")} aria-label="Thème plein soleil">
          ☀
        </button>
        <button type="button" onClick={() => applyTheme("night")} aria-label="Thème basse lumière">
          ☾
        </button>
      </span>
    </header>
  );
}

function MapArea() {
  const site = useSiteManifest();
  if (site.isError) return <p className="p-4">Site indisponible : {String(site.error)}</p>;
  if (!site.data) return <p className="p-4">Chargement du site…</p>;
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

/** Grand écran de l'habitat : carte au centre, panneaux latéraux. */
export function HabitatLayout({ mode = "habitat" }: { mode?: "habitat" | "tablet" }) {
  return (
    <Frame mode={mode}>
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

/** Tablette : même contenu, cibles tactiles d'au moins 76 px (tokens.css). */
export function TabletLayout() {
  return <HabitatLayout mode="tablet" />;
}

/** HUD de visière : plein écran à fort contraste, cinq éléments au plus (ENF-08). */
export function HudLayout() {
  const widgets = registry
    .flatMap((f) => f.hudWidgets)
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 5);
  const center = widgets.filter((w) => w.slot === "hud-center");
  const corner = widgets.filter((w) => w.slot === "hud-corner");
  return (
    <Frame mode="hud">
      <div className="relative flex flex-1 items-center justify-center">
        <div data-slot="hud-center" className="flex flex-col items-center gap-4">
          {center.map(({ id, component: C }) => (
            <C key={id} />
          ))}
          {widgets.length === 0 && <p>HUD : aucun élément (F5)</p>}
        </div>
        <div data-slot="hud-corner" className="absolute right-4 top-4 flex flex-col gap-2">
          {corner.map(({ id, component: C }) => (
            <C key={id} />
          ))}
        </div>
        <Link to="/" className="absolute bottom-4 left-4 text-base">
          Quitter le HUD
        </Link>
      </div>
    </Frame>
  );
}

/** Vue 3D : rendue par la route /3d d'une fonctionnalité (F6), sinon un message. */
export function Terrain3dLayout() {
  const route = registry.flatMap((f) => f.routes).find((r) => r.path === "/3d");
  return (
    <Frame mode="3d">
      <TopBar />
      <div className="min-h-0 flex-1">{route ? <route.component /> : <p className="p-4">Vue 3D à venir (F6).</p>}</div>
    </Frame>
  );
}
