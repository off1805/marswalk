/**
 * Panneau du bas (F3) : en-tête avec les totaux de la variante, graphique du profil et
 * tableau des tronçons avec leur durée.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useShared } from "@/shared/store";
import { colors, textColors } from "@/shared/theme";
import { injectQueryClient } from "./mapLayers";
import { ProfileChart } from "./ProfileChart";
import {
  compareTotals,
  formatDistance,
  formatDuration,
  pointOfNoReturnM,
  segmentSpans,
  slopeBands,
  targetMarkers,
  type SegmentSpan,
} from "./profileData";
import { useProfileRoute } from "./useProfileRoute";

const VARIANT_LABEL: Record<string, string> = {
  safest: "Safest",
  fastest: "Fastest",
  science: "Science",
};

function Empty({ children }: { children: string }) {
  return (
    <section aria-label="Route profile" className="flex h-full items-center justify-center p-4">
      <p className="text-sm text-[var(--text-muted)]">{children}</p>
    </section>
  );
}

function SegmentTable({ spans, hoverM }: { spans: SegmentSpan[]; hoverM: number | null }) {
  const setHover = useShared((s) => s.setHoverDistance);
  const th = "w-px whitespace-nowrap pb-1 pl-2 text-right text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]";
  return (
    <table className="w-full border-separate border-spacing-0 text-xs" aria-label="Segments">
      <thead className="sticky top-0 bg-[var(--surface-solid)]">
        <tr>
          <th className="pb-1 text-left text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">Leg</th>
          <th className={th}>Dist.</th>
          <th className={th}>Walk</th>
          <th className={th}>Work</th>
          <th className={th}>+/− m</th>
          <th className={th}>Max</th>
        </tr>
      </thead>
      <tbody className="font-mono tabular-nums">
        {spans.map((s) => {
          const active = hoverM != null && hoverM >= s.fromM && hoverM <= s.toM;
          return (
            <tr
              key={s.index}
              data-testid={`segment-${s.index}`}
              aria-current={active || undefined}
              className={`cursor-default ${active ? "bg-[var(--surface-3)]" : "hover:bg-[var(--surface-2)]"}`}
              onMouseEnter={() => setHover((s.fromM + s.toM) / 2)}
              onMouseLeave={() => setHover(null)}
            >
              <td className="max-w-0 truncate border-t border-[var(--border)] py-1 pr-2 font-sans" title={`${s.fromLabel} → ${s.toLabel}`}>
                <span className="text-[var(--text-muted)]">{s.index + 1}</span> <span className="sr-only">{s.fromLabel} </span>→ {s.toLabel}
              </td>
              <td className="whitespace-nowrap border-t border-[var(--border)] py-1 pl-2 text-right">{formatDistance(s.distanceM)}</td>
              <td className="whitespace-nowrap border-t border-[var(--border)] py-1 pl-2 text-right">{formatDuration(s.walkS)}</td>
              <td className="whitespace-nowrap border-t border-[var(--border)] py-1 pl-2 text-right">{s.workS > 0 ? formatDuration(s.workS) : "—"}</td>
              <td className="whitespace-nowrap border-t border-[var(--border)] py-1 pl-2 text-right">
                +{Math.round(s.ascentM)}/−{Math.round(s.descentM)}
              </td>
              <td className="whitespace-nowrap border-t border-[var(--border)] py-1 pl-2 text-right">{s.maxSlopeDeg.toFixed(1)}°</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Stat({ label, children, title }: { label: string; children: ReactNode; title?: string }) {
  return (
    <span className="flex items-baseline gap-1.5 whitespace-nowrap" title={title}>
      <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">{label}</span>{" "}
      <span className="font-mono text-[13px] tabular-nums text-[var(--text)]">{children}</span>
    </span>
  );
}

type View = "chart" | "legs";

export function ProfilePanel() {
  const qc = useQueryClient();
  useEffect(() => injectQueryClient(qc), [qc]);

  const { plan, choice, targetNames, isLoading, isError } = useProfileRoute();
  const hoverM = useShared((s) => s.hoverDistanceM);
  const route = choice?.route;
  const [view, setView] = useState<View>("chart");

  const derived = useMemo(() => {
    if (!route || !plan) return null;
    const spans = segmentSpans(route, targetNames);
    return {
      spans,
      bands: slopeBands(route.profile, {
        penaltyDeg: plan.settings.penalty_slope_deg,
        maxDeg: plan.settings.max_slope_deg,
      }),
      targets: targetMarkers(spans),
      pnrM: pointOfNoReturnM(route),
      mismatches: compareTotals(route),
    };
  }, [route, plan, targetNames]);

  if (isError) return <Empty>Route unavailable.</Empty>;
  if (isLoading) return <Empty>Loading profile…</Empty>;
  if (!route || !plan || !derived) {
    return <Empty>Add targets to compute a route — its profile will appear here.</Empty>;
  }

  const t = route.totals;
  const lineColor = colors.route[route.variant] ?? colors.accent;
  const consistent = derived.mismatches.length === 0;
  const tab = (v: View, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={view === v}
      onClick={() => setView(v)}
      className={`h-6 rounded-full px-2.5 text-xs transition-colors ${
        view === v ? "bg-[var(--accent)] text-[var(--accent-ink)]" : "text-[var(--text-muted)] hover:text-[var(--text)]"
      }`}
    >
      {label}
    </button>
  );
  return (
    <section aria-label="Route profile" className="@container flex h-full min-h-0 flex-col px-4 pb-2 pt-2.5">
      <header className="flex items-center gap-x-5 gap-y-1">
        <h2 className="flex shrink-0 items-center gap-2 text-sm font-medium">
          <span aria-hidden="true" className="inline-block size-2.5 rounded-full" style={{ background: lineColor }} />
          {VARIANT_LABEL[route.variant] ?? route.variant}
          {choice.preview && (
            <span className="rounded-full border border-[var(--border)] px-2 py-px text-[11px] font-normal text-[var(--text-muted)]">
              Preview: no variant selected
            </span>
          )}
        </h2>
        <span data-testid="profile-totals" className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-5 gap-y-1 overflow-hidden">
          <Stat label="Dist.">{formatDistance(t.distance_m)}</Stat>
          <Stat
            label="Duration"
            title={`walk ${formatDuration(t.walk_time_s)}, work ${formatDuration(t.work_time_s)}`}
          >
            {formatDuration(t.duration_s)}
          </Stat>
          <Stat label="Climb">
            +{Math.round(t.ascent_m)} / −{Math.round(t.descent_m)} m
          </Stat>
          <Stat label="Max slope">{t.max_slope_deg.toFixed(1)}°</Stat>
        </span>
        <span role="tablist" aria-label="Profile view" className="flex shrink-0 gap-0.5 rounded-full border border-[var(--border)] p-0.5 @4xl:hidden">
          {tab("chart", "Chart")}
          {tab("legs", "Legs")}
        </span>
      </header>
      {!consistent && (
        <p role="alert" className="mt-1 text-xs font-semibold" style={{ color: textColors.caution }} data-testid="totals-check">
          ▲ Profile / variant mismatch: {derived.mismatches.map((m) => m.field).join(", ")}
        </p>
      )}
      <div className="mt-2 flex min-h-0 flex-1 gap-5">
        <div className={`min-h-0 min-w-0 flex-1 flex-col ${view === "chart" ? "flex" : "hidden @4xl:flex"}`}>
          <div className="min-h-0 flex-1">
            <ProfileChart
              profile={route.profile}
              spans={derived.spans}
              bands={derived.bands}
              targets={derived.targets}
              pointOfNoReturnM={derived.pnrM}
              lineColor={lineColor}
            />
          </div>
          <p className="flex flex-wrap items-center gap-x-4 pt-1 text-[11px] text-[var(--text-muted)]">
            <span>
              <span aria-hidden="true" className="mr-1.5 inline-block h-0.5 w-4 align-middle" style={{ background: lineColor }} />
              Elevation
            </span>
            <span>┅ Slope</span>
            <span style={{ color: textColors.caution }}>▲ ≥ {plan.settings.penalty_slope_deg}° penalised</span>
            <span style={{ color: textColors.danger }}>⛔ ≥ {plan.settings.max_slope_deg}° forbidden</span>
            {consistent && (
              <span className="ml-auto" data-testid="totals-check" title="Profile totals consistent with the variant">
                ✓ Totals consistent
              </span>
            )}
          </p>
        </div>
        <div className={`min-h-0 overflow-y-auto overscroll-contain @4xl:block @4xl:w-[30rem] @4xl:shrink-0 ${view === "legs" ? "block w-full" : "hidden"}`}>
          <SegmentTable spans={derived.spans} hoverM={hoverM} />
        </div>
      </div>
    </section>
  );
}
