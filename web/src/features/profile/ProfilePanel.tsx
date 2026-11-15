/**
 * Panneau du bas (F3) : en-tête avec les totaux de la variante, graphique du profil et
 * tableau des tronçons avec leur durée.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useShared } from "@/shared/store";
import { colors } from "@/shared/theme";
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
  return (
    <table className="w-full text-[11px] leading-tight" aria-label="Segments">
      <thead className="text-left text-[var(--text-muted)]">
        <tr>
          <th className="pr-2">Segment</th>
          <th className="pr-2 text-right">Distance</th>
          <th className="pr-2 text-right">Walk</th>
          <th className="pr-2 text-right">Work</th>
          <th className="pr-2 text-right">Asc / Desc</th>
          <th className="text-right">Max slope</th>
        </tr>
      </thead>
      <tbody>
        {spans.map((s) => {
          const active = hoverM != null && hoverM >= s.fromM && hoverM <= s.toM;
          return (
            <tr
              key={s.index}
              data-testid={`segment-${s.index}`}
              aria-current={active || undefined}
              className={active ? "bg-[var(--border)]" : undefined}
              onMouseEnter={() => setHover((s.fromM + s.toM) / 2)}
              onMouseLeave={() => setHover(null)}
            >
              <td className="pr-2">
                {s.index + 1}. {s.fromLabel} → {s.toLabel}
              </td>
              <td className="pr-2 whitespace-nowrap text-right">{formatDistance(s.distanceM)}</td>
              <td className="pr-2 whitespace-nowrap text-right">{formatDuration(s.walkS)}</td>
              <td className="pr-2 whitespace-nowrap text-right">{s.workS > 0 ? formatDuration(s.workS) : "—"}</td>
              <td className="pr-2 whitespace-nowrap text-right">
                +{Math.round(s.ascentM)} / −{Math.round(s.descentM)} m
              </td>
              <td className="whitespace-nowrap text-right">{s.maxSlopeDeg.toFixed(1)}°</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function ProfilePanel() {
  const qc = useQueryClient();
  useEffect(() => injectQueryClient(qc), [qc]);

  const { plan, choice, targetNames, isLoading, isError } = useProfileRoute();
  const hoverM = useShared((s) => s.hoverDistanceM);
  const route = choice?.route;

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
  return (
    <section aria-label="Route profile" className="flex h-full min-h-0 flex-col gap-1 px-3 py-2">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
        <h2 className="font-bold">
          Profile · <span style={{ color: lineColor }}>{VARIANT_LABEL[route.variant] ?? route.variant}</span>
        </h2>
        {choice.preview && (
          <span className="text-xs text-[var(--text-muted)]">
            Preview: no variant selected
          </span>
        )}
        <span data-testid="profile-totals" className="flex flex-wrap gap-x-3">
          <span>{formatDistance(t.distance_m)}</span>
          <span>Duration {formatDuration(t.duration_s)}</span>
          <span>
            (walk {formatDuration(t.walk_time_s)}, work {formatDuration(t.work_time_s)})
          </span>
          <span>
            Ascent {Math.round(t.ascent_m)} m · Descent {Math.round(t.descent_m)} m
          </span>
          <span>Max slope {t.max_slope_deg.toFixed(1)}°</span>
        </span>
        {derived.mismatches.length === 0 ? (
          <span className="text-xs text-[var(--text-muted)]" data-testid="totals-check">
            ✓ Profile totals consistent with variant
          </span>
        ) : (
          <span role="alert" className="text-xs font-bold" style={{ color: colors.caution }} data-testid="totals-check">
            ▲ Profile / variant mismatch:{" "}
            {derived.mismatches.map((m) => m.field).join(", ")}
          </span>
        )}
        <span className="ml-auto flex gap-3 text-xs">
          <span>
            <span style={{ color: lineColor }}>━</span> elevation ·{" "}
            <span className="text-[var(--text-muted)]">┅</span> slope
          </span>
          <span style={{ color: colors.caution }}>▲ slope ≥ {plan.settings.penalty_slope_deg}°</span>
          <span style={{ color: colors.danger }}>⛔ slope ≥ {plan.settings.max_slope_deg}°</span>
        </span>
      </header>
      <div className="flex min-h-0 flex-1 gap-3">
        <div className="min-h-0 min-w-0 flex-1">
          <ProfileChart
            profile={route.profile}
            spans={derived.spans}
            bands={derived.bands}
            targets={derived.targets}
            pointOfNoReturnM={derived.pnrM}
            lineColor={lineColor}
          />
        </div>
        <div className="w-[34rem] shrink-0 overflow-y-auto">
          <SegmentTable spans={derived.spans} hoverM={hoverM} />
        </div>
      </div>
    </section>
  );
}
