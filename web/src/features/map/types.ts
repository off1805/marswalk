/**
 * Types et interfaces pour la fonctionnalité F1 : Carte et couches.
 * Respecte les principes SOLID (Interface Segregation Principle).
 */
import type { LayerInfo, PointQuery } from "@/shared/api/client";
import type { LayerView } from "@/shared/store";

export type LayerKind = LayerInfo["kind"];
export type PointValue = PointQuery["values"][number];

export interface LayerControlProps {
  layer: LayerInfo;
  view: LayerView;
  onToggleVisibility: (visible: boolean) => void;
  onChangeOpacity: (opacity: number) => void;
}

export interface LegendViewProps {
  legend: LayerInfo["legend"];
  unit?: string | null;
}

export interface QueryDetailsProps {
  query: PointQuery;
  onClose?: () => void;
}

export interface PointValueRowProps {
  pointValue: PointValue;
}

export type LayerKindGroup = {
  kind: LayerKind;
  title: string;
  layers: LayerInfo[];
};
