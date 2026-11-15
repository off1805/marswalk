/**
 * Option ECharts du profil (pure, testable sans canevas) : altitude et pente en fonction de la
 * distance, bandes de pente pénalisée (orange) et interdite (rouge), tronçons avec leur durée,
 * cibles, point de non-retour et repère de survol.
 *
 * ENF-06 : la couleur n'est jamais le seul indice. Les bandes portent une icône et un texte
 * (« ▲ 12° », « ⛔ 24° »), les cibles un losange et leur nom.
 */
import type { EChartsCoreOption } from "echarts/core";
import { alertLevels, colors } from "@/shared/theme";
import {
  formatDistance,
  formatDuration,
  type ProfileSample,
  type SegmentSpan,
  type SlopeBand,
  type TargetMarker,
} from "./profileData";

export interface ProfileChartInput {
  profile: ProfileSample[];
  spans: SegmentSpan[];
  bands: SlopeBand[];
  targets: TargetMarker[];
  pointOfNoReturnM: number | null;
  /** Repère de survol venu de la carte ou de la 3D ; null s'il n'y en a pas. */
  hoverDistanceM: number | null;
  lineColor: string;
  dark?: boolean;
}

const BAND_ALPHA = "40"; // ~25 % d'opacité, suffixe hexadécimal

/** Texte de l'infobulle pour un échantillon. */
export function tooltipText(sample: ProfileSample, span: SegmentSpan | undefined): string {
  const parts = [
    `<b>${formatDistance(sample.distance_m)}</b>`,
    `Elevation: ${sample.elevation_m == null ? "unknown" : `${sample.elevation_m.toFixed(1)} m`}`,
    `Slope: ${sample.slope_deg == null ? "unknown" : `${Math.abs(sample.slope_deg).toFixed(1)}°`}`,
    `Elapsed time: ${formatDuration(sample.time_s)}`,
  ];
  if (span) parts.push(`Segment ${span.index + 1}: ${span.fromLabel} → ${span.toLabel}`);
  return parts.join("<br/>");
}

export function buildChartOption(input: ProfileChartInput): EChartsCoreOption {
  const { profile, spans, bands, targets } = input;
  const text = input.dark ? "#e6e6e6" : "#1a1a1a";
  const muted = input.dark ? "#a0a0a0" : "#555555";
  const grid = input.dark ? "#3a3a3a" : "#dddddd";
  const elevation = profile.map((p) => [p.distance_m, p.elevation_m]);
  const slope = profile.map((p) => [p.distance_m, p.slope_deg == null ? null : Math.abs(p.slope_deg)]);
  const maxX = profile.length ? profile[profile.length - 1]!.distance_m : 0;

  const bandAreas = bands.map((b) => {
    const lvl = alertLevels[b.level];
    return [
      {
        name: `${lvl.icon} ${Math.round(b.maxSlopeDeg)}°`,
        xAxis: b.fromM,
        itemStyle: { color: `${lvl.color}${BAND_ALPHA}` },
        label: { position: "insideBottom", color: lvl.color, fontWeight: "bold" },
      },
      { xAxis: b.toM },
    ];
  });

  const segmentAreas = spans.map((s) => [
    {
      name: `${s.index + 1} · ${formatDuration(s.walkS)}`,
      xAxis: s.fromM,
      itemStyle: { color: "transparent" },
      label: { position: "insideTop", color: muted, fontSize: 11 },
    },
    { xAxis: s.toM },
  ]);

  const lines: Record<string, unknown>[] = [
    // Fins de tronçon (sauf la dernière, qui est l'arrivée)
    ...spans.slice(0, -1).map((s) => ({
      xAxis: s.toM,
      lineStyle: { color: grid, type: "dashed", width: 1 },
      label: { show: false },
    })),
    ...targets.map((t) => ({
      name: `◆ ${t.label}`,
      xAxis: t.distanceM,
      lineStyle: { color: colors.accent, type: "solid", width: 2 },
      // Texte vertical le long du repère : deux cibles proches ne se chevauchent pas.
      label: { formatter: "{b}", position: "insideEndTop", color: text, fontSize: 11 },
    })),
  ];
  if (input.pointOfNoReturnM != null) {
    lines.push({
      name: "⚑ Point of no return",
      xAxis: input.pointOfNoReturnM,
      lineStyle: { color: colors.danger, type: "dotted", width: 2 },
      label: { formatter: "{b}", position: "insideEndTop", color: colors.danger, fontSize: 11 },
    });
  }
  if (input.hoverDistanceM != null) {
    lines.push({
      name: "hover",
      xAxis: input.hoverDistanceM,
      lineStyle: { color: text, type: "solid", width: 1.5 },
      label: { show: false },
    });
  }

  return {
    animation: false,
    textStyle: { color: text },
    grid: { left: 56, right: 48, top: 24, bottom: 32 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", snap: true },
      // Le texte est fourni par le composant, qui connaît le tronçon de chaque échantillon.
    },
    xAxis: {
      type: "value",
      min: 0,
      max: maxX,
      name: "Distance",
      nameLocation: "middle",
      nameGap: 22,
      axisLabel: { color: muted, formatter: (v: number) => formatDistance(v) },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        name: "Elevation (m)",
        scale: true,
        axisLabel: { color: muted },
        nameTextStyle: { color: muted },
        splitLine: { lineStyle: { color: grid } },
      },
      {
        type: "value",
        name: "Slope (°)",
        min: 0,
        axisLabel: { color: muted },
        nameTextStyle: { color: muted },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "Elevation",
        type: "line",
        yAxisIndex: 0,
        data: elevation,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { color: input.lineColor, width: 2 },
        itemStyle: { color: input.lineColor },
        areaStyle: { color: `${input.lineColor}22` },
        markArea: { silent: true, data: bandAreas },
        markLine: { silent: true, symbol: "none", data: lines, animation: false },
      },
      {
        name: "Slope",
        type: "line",
        yAxisIndex: 1,
        data: slope,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { color: muted, width: 1, type: "dashed" },
        itemStyle: { color: muted },
        markArea: { silent: true, data: segmentAreas },
      },
    ],
  };
}
