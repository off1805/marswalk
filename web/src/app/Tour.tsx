/**
 * Guided tour of the console. Runs once on first visit, and again from the header's
 * Guide button. Each step lights up one part of the console (elements tagged
 * data-tour="…") and explains what it is for, in workflow order.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Section } from "./dock";
import { markTourSeen, tourSeen, useConsole } from "./uiStore";
import { useShared } from "@/shared/store";

interface Step {
  /** data-tour value of the element to light up; none centers the card. */
  target?: string;
  title: string;
  body: string;
  /** Only meaningful on the map view. */
  mapOnly?: boolean;
  /** Prepares the console before the step is shown (opens a section, a sheet…). */
  before?: (ctx: { phone: boolean; evaInRail: boolean; sections: Section[] }) => void;
}

const open = (id: string | null) => useConsole.getState().setSection(id);

const STEPS: Step[] = [
  {
    title: "Welcome to Marswalk",
    body: "Plan a safe walking EVA across the site: choose science targets, compare routes, and keep an eye on your margins while you walk. This tour takes about a minute.",
  },
  {
    target: "stage",
    mapOnly: true,
    title: "The site, edge to edge",
    body: "Orbital imagery of the landing site fills the screen. Drag to pan, scroll or pinch to zoom. Everything you plan is drawn here.",
    before: () => open(null),
  },
  {
    target: "rail",
    mapOnly: true,
    title: "One tool at a time",
    body: "Tools follow the planning workflow, top to bottom. Open one to work in it; select it again, or close it, to give the screen back to the map.",
  },
  {
    target: "drawer",
    mapOnly: true,
    title: "Read the terrain",
    body: "Layers holds the display presets (safety, science, navigation) and the hazard maps: slope, roughness and obstacles with their safety buffer.",
    before: () => open("layers"),
  },
  {
    target: "drawer",
    mapOnly: true,
    title: "Choose targets, compare routes",
    body: "Add the stops you want to visit. Marswalk computes the safest, fastest and most science-rich variants; choose one to make it the active route.",
    before: () => open("targets"),
  },
  {
    target: "eva",
    mapOnly: true,
    title: "Your margins",
    body: "Time left before the point of no return, consumable reserves and radiation dose for the active plan. During the walk, this is the pane you watch.",
    before: ({ evaInRail }) => {
      if (evaInRail) open("eva");
      else {
        open(null);
        useConsole.getState().setEvaCollapsed(false);
      }
    },
  },
  {
    target: "alerts",
    mapOnly: true,
    title: "Alerts",
    body: "Hazards show up here, most severe first, each with the action to take. Acknowledge an alert to confirm the crew has seen it.",
    before: ({ phone }) => phone && open(null),
  },
  {
    target: "profile",
    mapOnly: true,
    title: "Elevation profile",
    body: "Climbs and slopes along the active route, leg by leg. Hover the chart to find the same point on the map.",
    before: () => useConsole.getState().setProfileOpen(true),
  },
  {
    target: "views",
    title: "Time and views",
    body: "The clock gives the sol and the local mean solar time at the site. Switch to 3D to fly over the terrain along your route.",
  },
  {
    target: "guide",
    title: "You're set",
    body: "Reopen this tour any time from Guide. Field log and Export are there for the walk itself and for the debrief.",
  },
];

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

const PAD = 6;
const CARD_W = 340;

function measure(target: string | undefined): Rect | null {
  if (!target) return null;
  const el = document.querySelector<HTMLElement>(`[data-tour="${target}"]`);
  if (!el || el.closest("[aria-hidden='true']")) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  return { x: r.left - PAD, y: r.top - PAD, w: r.width + PAD * 2, h: r.height + PAD * 2 };
}

function sameRect(a: Rect | null, b: Rect | null) {
  if (!a || !b) return a === b;
  return Math.abs(a.x - b.x) < 0.5 && Math.abs(a.y - b.y) < 0.5 && Math.abs(a.w - b.w) < 0.5 && Math.abs(a.h - b.h) < 0.5;
}

/** Card position: beside the lit element where it fits, else below/above, else centered. */
function place(rect: Rect | null, cardH: number): { left: number; top: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const w = Math.min(CARD_W, vw - 24);
  const center = { left: (vw - w) / 2, top: Math.max(12, (vh - cardH) / 2) };
  if (!rect) return center;
  const clampY = (y: number) => Math.min(Math.max(12, y), vh - cardH - 12);
  const clampX = (x: number) => Math.min(Math.max(12, x), vw - w - 12);
  const gap = 16;
  // A lit area wider than most of the screen (the stage): put the card inside it.
  if (rect.w > vw * 0.55 && rect.h > vh * 0.5) return { left: clampX(rect.x + rect.w / 2 - w / 2), top: clampY(rect.y + rect.h / 2 - cardH / 2) };
  if (rect.x + rect.w + gap + w <= vw - 12) return { left: rect.x + rect.w + gap, top: clampY(rect.y) };
  if (rect.x - gap - w >= 12) return { left: rect.x - gap - w, top: clampY(rect.y) };
  if (rect.y + rect.h + gap + cardH <= vh - 12) return { left: clampX(rect.x), top: rect.y + rect.h + gap };
  if (rect.y - gap - cardH >= 12) return { left: clampX(rect.x), top: rect.y - gap - cardH };
  return center;
}

/** Opens the tour once, on first visit, when the console has something to show. */
export function useAutoTour(ready: boolean) {
  const setTourOpen = useConsole((s) => s.setTourOpen);
  useEffect(() => {
    if (!ready || tourSeen()) return;
    const t = window.setTimeout(() => setTourOpen(true), 700);
    return () => window.clearTimeout(t);
  }, [ready, setTourOpen]);
}

export function Tour({ sections, phone, evaInRail }: { sections: Section[]; phone: boolean; evaInRail: boolean }) {
  const isOpen = useConsole((s) => s.tourOpen);
  const setTourOpen = useConsole((s) => s.setTourOpen);
  const mode = useShared((s) => s.mode);
  const steps = STEPS.filter((s) => mode === "map" || !s.mapOnly);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [cardH, setCardH] = useState(220);
  const cardRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const step = steps[Math.min(index, steps.length - 1)]!;
  const last = index >= steps.length - 1;
  // Where EVA safety lives in the rail, its step lights up the drawer instead.
  const target = step.target === "eva" && evaInRail ? "drawer" : step.target;

  const close = useCallback(() => {
    markTourSeen();
    setTourOpen(false);
    setIndex(0);
  }, [setTourOpen]);

  // Prepare the console for the step.
  useEffect(() => {
    if (!isOpen) return;
    step.before?.({ phone, evaInRail, sections });
    // sections changes identity with the mode only; the step is what matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, index]);

  // Follow the lit element while panes animate or the window resizes.
  useEffect(() => {
    if (!isOpen) return;
    let raf = 0;
    let prev: Rect | null = null;
    const tick = () => {
      const r = measure(target);
      if (!sameRect(r, prev)) {
        prev = r;
        setRect(r);
      }
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [isOpen, target]);

  useLayoutEffect(() => {
    if (cardRef.current) setCardH(cardRef.current.offsetHeight);
  }, [isOpen, index, rect]);

  useEffect(() => {
    if (isOpen) titleRef.current?.focus();
  }, [isOpen, index]);

  if (!isOpen) return null;

  const next = () => (last ? close() : setIndex((i) => i + 1));
  const back = () => setIndex((i) => Math.max(0, i - 1));

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      next();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      back();
    } else if (e.key === "Tab" && cardRef.current) {
      const focusables = cardRef.current.querySelectorAll<HTMLElement>("button, [tabindex='-1']");
      const first = focusables[0];
      const lastEl = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        lastEl?.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        first?.focus();
      }
    }
  };

  const pos = place(rect, cardH);
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const glide = "duration-[520ms] ease-[var(--ease-out-expo)]";

  return (
    <div className="fixed inset-0 z-50" onKeyDown={onKeyDown}>
      {/* Scrim with a cut-out over the lit element. */}
      <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <mask id="tour-cutout">
            <rect width={vw} height={vh} fill="white" />
            {rect && (
              <rect
                x={rect.x}
                y={rect.y}
                width={rect.w}
                height={rect.h}
                rx="16"
                fill="black"
                className={`transition-all ${glide}`}
              />
            )}
          </mask>
        </defs>
        <rect width={vw} height={vh} fill="rgb(8 5 3 / 0.66)" mask="url(#tour-cutout)" />
      </svg>
      {rect && (
        <div
          aria-hidden="true"
          className={`pointer-events-none absolute rounded-[16px] border border-[var(--focus)] shadow-[0_0_0_4px_rgb(243_196_139/0.14)] transition-all ${glide}`}
          style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}
        />
      )}
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
        className={`absolute rounded-2xl border border-[var(--border-strong)] bg-[var(--surface-solid)] p-5 text-[var(--text)] shadow-[0_24px_60px_-16px_rgb(0_0_0/0.7)] transition-[left,top] ${glide}`}
        style={{ left: pos.left, top: pos.top, width: Math.min(CARD_W, vw - 24) }}
      >
        <div className="mb-3 flex items-center gap-3">
          <span className="font-mono text-xs tabular-nums text-[var(--text-muted)]">
            {String(index + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}
          </span>
          <span className="h-px flex-1 overflow-hidden bg-[var(--border)]">
            <span
              className={`block h-full bg-[var(--focus)] transition-[width] ${glide}`}
              style={{ width: `${((index + 1) / steps.length) * 100}%` }}
            />
          </span>
        </div>
        <h2 id="tour-title" ref={titleRef} tabIndex={-1} className="text-lg font-medium leading-snug outline-none text-balance">
          {step.title}
        </h2>
        <p id="tour-body" className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
          {step.body}
        </p>
        <div className="mt-5 flex items-center gap-2">
          {!last && (
            <button
              type="button"
              onClick={close}
              className="mr-auto text-sm text-[var(--text-muted)] underline-offset-4 hover:text-[var(--text)] hover:underline"
            >
              Skip tour
            </button>
          )}
          {index > 0 && (
            <button
              type="button"
              onClick={back}
              className={`${last ? "mr-auto" : ""} h-9 rounded-lg border border-[var(--border)] px-3 text-sm hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]`}
            >
              Back
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              if (last) open("targets");
              next();
            }}
            className="h-9 rounded-lg bg-[var(--accent)] px-4 text-sm font-medium text-[var(--accent-ink)] hover:brightness-110"
          >
            {index === 0 ? "Show me around" : last ? "Start planning" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
