/**
 * Web console layouts: the map (edge to edge, with floating tool panes) and the 3D view.
 *
 * The map is the backdrop. Around it: a header (site, Martian time, views), a rail that
 * opens one tool section at a time, the EVA safety pane pinned on the right, and the
 * elevation profile folded at the bottom. The space left free between the panes is the
 * "stage": map overlays and MapLibre controls stay inside it (CSS variables --stage-*).
 */
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { NavLink } from "react-router";
import { buildSections, type DockPanel, type Section } from "./dock";
import { Icon, type IconName } from "./icons";
import { MapView } from "./MapView";
import { registry } from "./registry";
import { SitePicker } from "./SitePicker";
import { Slot } from "./Slot";
import { Tour, useAutoTour } from "./Tour";
import { useConsole } from "./uiStore";
import { useHealth, useMarsClock, useSiteManifest } from "@/shared/hooks";
import { useShared } from "@/shared/store";
import { applyTheme, type Theme } from "@/shared/theme";

/* ------------------------------------------------------------------ geometry */

/** phone: rail at the bottom. tablet: EVA safety moves into the rail. desktop: EVA pinned. */
type Size = "phone" | "tablet" | "desktop";

function useSize(): Size {
  const get = (): Size => {
    if (typeof window === "undefined") return "desktop";
    const w = window.innerWidth;
    return w < 768 ? "phone" : w < 1100 ? "tablet" : "desktop";
  };
  const [size, setSize] = useState<Size>(get);
  useEffect(() => {
    const on = () => setSize(get());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return size;
}

const GAP = 12;
const HEADER = 60;
const RAIL = 56;
const SHEET_CLOSED = 44;
const SHEET_OPEN = 260;

interface Geometry {
  drawer: CSSProperties;
  eva: CSSProperties | null;
  sheet: CSSProperties;
  stage: { top: number; right: number; bottom: number; left: number };
}

function geometry(size: Size, drawerOpen: boolean, evaCollapsed: boolean, profileOpen: boolean): Geometry {
  const sheetH = profileOpen ? SHEET_OPEN : SHEET_CLOSED;
  if (size === "phone") {
    const railH = 60;
    const bottom = GAP + railH + 8;
    return {
      drawer: { left: 8, right: 8, bottom, maxHeight: "62vh" },
      eva: null,
      sheet: { left: 8, right: 8, bottom, height: sheetH },
      stage: { top: 56, right: 8, bottom: bottom + sheetH + 8, left: 8 },
    };
  }
  const wide = typeof window !== "undefined" && window.innerWidth >= 1440;
  const drawerW = wide ? 380 : 340;
  const evaW = wide ? 344 : 312;
  const top = HEADER + 8;
  const left = GAP + RAIL + (drawerOpen ? 8 + drawerW : 0) + GAP;
  const pinned = size === "desktop";
  const evaRight = pinned ? GAP + evaW + GAP : GAP;
  return {
    drawer: { top, bottom: GAP, left: GAP + RAIL + 8, width: drawerW },
    eva: pinned ? { top, right: GAP, width: evaW, maxHeight: `calc(100% - ${top + GAP}px)` } : null,
    sheet: { left, right: evaCollapsed ? GAP : evaRight, bottom: GAP, height: sheetH },
    stage: { top, right: evaRight, bottom: GAP + sheetH + GAP, left },
  };
}

/* ------------------------------------------------------------------ header */

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme as Theme | undefined) ?? "night",
  );
  const toggle = () => {
    const next: Theme = theme === "night" ? "day" : "night";
    applyTheme(next);
    setTheme(next);
  };
  return [theme, toggle];
}

function HeaderButton({
  label,
  icon,
  onClick,
  children,
  tour,
}: {
  label: string;
  icon: IconName;
  onClick: () => void;
  children?: ReactNode;
  tour?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      data-tour={tour}
      className="inline-flex h-9 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--text)] backdrop-blur-md transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--surface-solid)]"
    >
      <Icon name={icon} size={17} />
      {children}
    </button>
  );
}

function ViewSwitch() {
  const item = (to: string, label: string, icon: IconName) => (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[13px] transition-colors ${
          isActive
            ? "bg-[var(--accent)] text-[var(--accent-ink)]"
            : "text-[var(--text-muted)] hover:text-[var(--text)]"
        }`
      }
    >
      <Icon name={icon} size={15} />
      {label}
    </NavLink>
  );
  return (
    <nav
      aria-label="Views"
      data-tour="views"
      className="inline-flex items-center gap-0.5 rounded-full border border-[var(--border)] bg-[var(--surface)] p-1 backdrop-blur-md"
    >
      {item("/", "Map", "map")}
      {item("/3d", "3D", "cube")}
    </nav>
  );
}

function MarsClock({ compact }: { compact?: boolean }) {
  const clock = useMarsClock();
  if (!clock.data) return null;
  return (
    <div aria-label="Martian time" data-tour="clock" className="flex items-baseline gap-3 leading-none">
      <span className="flex items-baseline gap-1.5">
        <span className="label-caps">Sol</span>
        <span className="font-mono text-lg text-[var(--text)] tabular-nums">{clock.data.sol}</span>
      </span>
      {!compact && (
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-lg text-[var(--text)] tabular-nums">{clock.data.lmst}</span>
          <span className="label-caps">LMST</span>
        </span>
      )}
    </div>
  );
}

function LinkStatus() {
  const health = useHealth();
  const ok = health.isSuccess;
  return (
    <span aria-label="API status" className="hidden items-center gap-2 text-xs text-[var(--text-muted)] lg:inline-flex">
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${ok ? "bg-[var(--color-ok)]" : "border border-[var(--text-muted)]"}`}
      />
      {ok ? "Link nominal" : "API offline"}
    </span>
  );
}

function TopBar({ overlay, size }: { overlay: boolean; size: Size }) {
  const site = useSiteManifest();
  const [theme, toggleTheme] = useTheme();
  const setTourOpen = useConsole((s) => s.setTourOpen);
  const phone = size === "phone";
  return (
    <header
      className={`z-30 flex items-center gap-3 px-3 sm:gap-5 sm:px-4 ${
        overlay
          ? "pointer-events-none absolute inset-x-0 top-0 [&>*]:pointer-events-auto"
          : "relative border-b border-[var(--border)] bg-[var(--surface-solid)]"
      }`}
      style={{ height: phone ? 56 : HEADER }}
    >
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex items-center gap-2">
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="6.2" fill="var(--mars-tint)" />
            <ellipse cx="12" cy="12" rx="10.5" ry="3.6" fill="none" stroke="var(--text)" strokeWidth="1.1" opacity=".7" transform="rotate(-18 12 12)" />
          </svg>
          <strong className="text-[13px] font-semibold tracking-[0.24em] text-[var(--text)]">MARSWALK</strong>
        </span>
        {!phone && (
          <span className="flex min-w-0 items-center gap-2 border-l border-[var(--border)] pl-3">
            <span className="truncate text-[13px] text-[var(--text-muted)]">{site.data?.name ?? "Loading site…"}</span>
            <SitePicker />
          </span>
        )}
      </div>
      <div className="flex flex-1 justify-center">
        <ViewSwitch />
      </div>
      <div className="flex items-center gap-3 sm:gap-4">
        <MarsClock compact={phone} />
        <LinkStatus />
        <HeaderButton
          label={theme === "night" ? "Switch to day theme (full sun)" : "Switch to night theme"}
          icon={theme === "night" ? "sun" : "moon"}
          onClick={toggleTheme}
        />
        <HeaderButton label="Open the guided tour" icon="help" onClick={() => setTourOpen(true)} tour="guide">
          {!phone && "Guide"}
        </HeaderButton>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ dock */

function Rail({ sections, phone }: { sections: Section[]; phone: boolean }) {
  const open = useConsole((s) => s.section);
  const toggle = useConsole((s) => s.toggleSection);
  return (
    <nav
      aria-label="Tools"
      data-tour="rail"
      className={`pane absolute z-20 flex gap-1 p-1.5 ${
        phone ? "inset-x-2 bottom-3 h-[56px] items-center justify-between gap-0.5 overflow-x-auto p-1" : "flex-col"
      }`}
      style={phone ? undefined : { top: HEADER + 8, left: GAP, width: RAIL }}
    >
      {sections.map((s) => {
        const active = open === s.id;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => toggle(s.id)}
            aria-label={s.title}
            aria-expanded={active}
            aria-controls="tool-drawer"
            data-tour={`rail-${s.id}`}
            className={`group relative grid ${phone ? "size-10" : "size-11"} shrink-0 place-items-center rounded-[10px] transition-colors duration-150 ${
              active
                ? "bg-[var(--accent)] text-[var(--accent-ink)]"
                : "text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--text)]"
            }`}
          >
            <Icon name={s.icon} size={20} />
            {!phone && (
              <span
                role="presentation"
                className="pointer-events-none absolute left-full top-1/2 ml-3 -translate-x-1 -translate-y-1/2 whitespace-nowrap rounded-md border border-[var(--border)] bg-[var(--surface-solid)] px-2 py-1 text-xs text-[var(--text)] opacity-0 shadow-[var(--shadow)] transition duration-150 group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100"
              >
                {s.title}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}

function Panels({ panels }: { panels: DockPanel[] }) {
  return (
    <>
      {panels.map(({ key, component: C }) => (
        <C key={key} />
      ))}
    </>
  );
}

function Drawer({ sections, style }: { sections: Section[]; style: CSSProperties }) {
  const openId = useConsole((s) => s.section);
  const setSection = useConsole((s) => s.setSection);
  const section = sections.find((s) => s.id === openId) ?? null;
  // Remember the last section so it stays mounted (with its state) while folded away.
  const [last, setLast] = useState<Section | null>(section);
  useEffect(() => {
    if (section) setLast(section);
  }, [section]);
  const shown = section ?? last;
  if (!shown) return null;
  return (
    <aside
      id="tool-drawer"
      aria-label={shown.title}
      aria-hidden={!section}
      inert={!section}
      data-tour="drawer"
      className={`pane absolute z-20 flex flex-col overflow-hidden transition-[opacity,transform,filter] duration-[380ms] ease-[var(--ease-out-expo)] ${
        section ? "translate-x-0 opacity-100 blur-0" : "pointer-events-none -translate-x-3 opacity-0 blur-[2px]"
      }`}
      style={style}
    >
      <div className="flex items-start gap-3 border-b border-[var(--border)] px-4 pb-3 pt-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-medium text-[var(--text)]">{shown.title}</h2>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">{shown.hint}</p>
        </div>
        <button
          type="button"
          onClick={() => setSection(null)}
          aria-label={`Close ${shown.title}`}
          className="grid size-7 place-items-center rounded-md text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--text)]"
        >
          <Icon name="close" size={16} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <Panels panels={shown.panels} />
      </div>
    </aside>
  );
}

function EvaPane({ panels, style }: { panels: DockPanel[]; style: CSSProperties }) {
  const collapsed = useConsole((s) => s.evaCollapsed);
  const setCollapsed = useConsole((s) => s.setEvaCollapsed);
  if (panels.length === 0) return null;
  return (
    <aside aria-label="EVA safety" data-tour="eva" className="pane absolute z-20 flex flex-col overflow-hidden" style={style}>
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
        className="flex items-center gap-2.5 px-4 py-3 text-left hover:bg-[var(--surface-2)]"
      >
        <Icon name="shield" size={18} className="text-[var(--text-muted)]" />
        <span className="flex-1 text-[15px] font-medium text-[var(--text)]">EVA safety</span>
        <Icon
          name="chevron"
          size={16}
          className={`text-[var(--text-muted)] transition-transform duration-300 ${collapsed ? "rotate-90" : "-rotate-90"}`}
        />
      </button>
      <div hidden={collapsed} className="min-h-0 flex-1 overflow-y-auto overscroll-contain border-t border-[var(--border)]">
        <Panels panels={panels} />
      </div>
    </aside>
  );
}

function ProfileSheet({ style }: { style: CSSProperties }) {
  const open = useConsole((s) => s.profileOpen);
  const setOpen = useConsole((s) => s.setProfileOpen);
  const route = useShared((s) => s.activeRouteId);
  return (
    <section
      aria-label="Elevation profile"
      data-tour="profile"
      className="pane absolute z-10 flex flex-col overflow-hidden transition-[height,left,right] duration-[380ms] ease-[var(--ease-out-expo)]"
      style={style}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex h-11 shrink-0 items-center gap-2.5 px-4 text-left hover:bg-[var(--surface-2)]"
      >
        <Icon name="mountain" size={17} className="text-[var(--text-muted)]" />
        <span className="whitespace-nowrap text-sm font-medium text-[var(--text)]">Elevation profile</span>
        <span className="hidden truncate text-xs sm:inline text-[var(--text-muted)]">
          {route ? "· active route" : "· slopes and climbs along the route"}
        </span>
        <Icon
          name="chevron"
          size={16}
          className={`ml-auto text-[var(--text-muted)] transition-transform duration-300 ${open ? "rotate-90" : "-rotate-90"}`}
        />
      </button>
      <div hidden={!open} className="min-h-0 flex-1 border-t border-[var(--border)]">
        <Slot name="bottom" className="h-full" />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ map */

function MapArea() {
  const site = useSiteManifest();
  if (site.isError)
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div>
          <p className="text-base text-[var(--text)]">Site imagery is unavailable.</p>
          <p className="mt-1 text-sm text-[var(--text-muted)]">{String(site.error)} · Check the API link, then reload.</p>
        </div>
      </div>
    );
  if (!site.data)
    return (
      <div className="grid h-full place-items-center">
        <p className="label-caps animate-pulse">Acquiring site imagery…</p>
      </div>
    );
  return <MapView manifest={site.data} />;
}

/** Edge shading: keeps header and pane text legible over bright terrain. */
function Vignette() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-[1]">
      <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[var(--scrim)] to-transparent" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_45%,transparent_55%,var(--scrim)_100%)]" />
    </div>
  );
}

/** Web console over the map. */
export function MapLayout() {
  const size = useSize();
  const phone = size === "phone";
  const mode = useShared((s) => s.mode);
  const section = useConsole((s) => s.section);
  const evaCollapsed = useConsole((s) => s.evaCollapsed);
  const profileOpen = useConsole((s) => s.profileOpen);
  const evaInRail = size !== "desktop";
  const { sections, eva } = useMemo(() => buildSections(mode, evaInRail), [mode, evaInRail]);
  const drawerOpen = section !== null && sections.some((s) => s.id === section);
  const g = geometry(size, drawerOpen, evaCollapsed, profileOpen);
  const site = useSiteManifest();
  useAutoTour(Boolean(site.data));

  const stageVars = {
    "--stage-t": `${g.stage.top}px`,
    "--stage-r": `${g.stage.right}px`,
    "--stage-b": `${g.stage.bottom}px`,
    "--stage-l": `${g.stage.left}px`,
  } as CSSProperties;

  return (
    <div data-mode="map" className="relative h-full overflow-hidden bg-[var(--bg)]" style={stageVars}>
      <main className="absolute inset-0" data-tour="map">
        <MapArea />
      </main>
      <Vignette />
      <div
        data-tour="stage"
        className="pointer-events-none absolute z-10 transition-[left,right,bottom] duration-[380ms] ease-[var(--ease-out-expo)]"
        style={g.stage}
      >
        <Slot name="map-overlay" className="absolute inset-0 [&>*]:pointer-events-auto" />
        <div data-tour="alerts" className="pointer-events-none absolute left-0 right-0 top-10 flex justify-center sm:top-0 sm:pr-28 [&>*]:pointer-events-auto [&>*]:w-full [&>*]:max-w-[52rem]">
          <Slot name="top-banner" />
        </div>
      </div>
      <TopBar overlay size={size} />
      <Rail sections={sections} phone={phone} />
      <Drawer sections={sections} style={g.drawer} />
      {g.eva && <EvaPane panels={eva} style={g.eva} />}
      {!(phone && drawerOpen) && <ProfileSheet style={g.sheet} />}
      <Tour sections={sections} phone={phone} evaInRail={evaInRail} />
    </div>
  );
}

/** 3D view: rendered by the /3d route of a feature (F6), otherwise a placeholder. */
export function Terrain3dLayout() {
  const size = useSize();
  const route = registry.flatMap((f) => f.routes).find((r) => r.path === "/3d");
  return (
    <div data-mode="3d" className="flex h-full flex-col">
      <TopBar overlay={false} size={size} />
      <div className="relative min-h-0 flex-1">
        {route ? <route.component /> : <p className="p-4">3D view coming soon (F6).</p>}
      </div>
      <Tour sections={[]} phone={size === "phone"} evaInRail={size !== "desktop"} />
    </div>
  );
}
