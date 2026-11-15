/**
 * Graphique ECharts du profil. Le survol du graphique écrit `hoverDistanceM` dans le magasin
 * partagé ; un survol venu de la carte ou de la 3D s'affiche comme un repère vertical.
 */
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";
import { useShared } from "@/shared/store";
import { buildChartOption, tooltipText, type ProfileChartInput } from "./chartOption";
import { sampleIndexAt, type ProfileSample, type SegmentSpan } from "./profileData";

echarts.use([
  LineChart,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  SVGRenderer,
]);

type Props = Omit<ProfileChartInput, "hoverDistanceM" | "dark">;

interface AxisPointerEvent {
  axesInfo?: { axisDim: string; value: number }[];
}

function spanOf(spans: SegmentSpan[], sample: ProfileSample): SegmentSpan | undefined {
  return spans.find((s) => s.index === sample.segment_index);
}

export function ProfileChart(props: Props) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  /** Dernière distance écrite par ce graphique : on ne la redessine pas en repère externe. */
  const lastEmitted = useRef<number | null>(null);
  const profileRef = useRef(props.profile);
  profileRef.current = props.profile;

  const hover = useShared((s) => s.hoverDistanceM);
  const external = hover != null && hover !== lastEmitted.current ? hover : null;
  const dark =
    typeof document !== "undefined" && document.documentElement.dataset.theme === "night";

  const { profile, spans, bands, targets, pointOfNoReturnM, lineColor } = props;
  const option = useMemo(() => {
    const opt = buildChartOption({
      profile,
      spans,
      bands,
      targets,
      pointOfNoReturnM,
      lineColor,
      hoverDistanceM: external,
      dark,
    });
    const tooltip = opt.tooltip as Record<string, unknown>;
    tooltip.formatter = (params: { dataIndex: number }[] | { dataIndex: number }) => {
      const first = Array.isArray(params) ? params[0] : params;
      const sample = first ? profile[first.dataIndex] : undefined;
      return sample ? tooltipText(sample, spanOf(spans, sample)) : "";
    };
    return opt;
  }, [profile, spans, bands, targets, pointOfNoReturnM, lineColor, external, dark]);

  // Création et destruction du graphique
  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current, undefined, { renderer: "svg" });
    chart.current = c;

    const emit = (d: number | null) => {
      const { hoverDistanceM, setHoverDistance } = useShared.getState();
      lastEmitted.current = d;
      if (hoverDistanceM !== d) setHoverDistance(d);
    };
    c.on("updateAxisPointer", (e: unknown) => {
      const info = (e as AxisPointerEvent).axesInfo?.find((a) => a.axisDim === "x");
      if (!info) return;
      const samples = profileRef.current;
      const i = sampleIndexAt(samples, info.value);
      if (i >= 0) emit(samples[i]!.distance_m);
    });
    c.getZr().on("globalout", () => emit(null));

    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => c.resize()) : null;
    ro?.observe(el.current);
    return () => {
      ro?.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option]);

  return (
    <div
      ref={el}
      className="h-full min-h-0 w-full"
      role="img"
      aria-label="Elevation and slope profile along the route"
      data-testid="profile-chart"
    />
  );
}
