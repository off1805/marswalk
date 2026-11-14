/** Jetons de design côté JavaScript (deck.gl, ECharts), alignés sur tokens.css. */
export type AlertLevel = "info" | "caution" | "danger";
export type Rgb = [number, number, number];

export const colors = {
  info: "#0072b2",
  caution: "#e69f00",
  danger: "#d55e00",
  ok: "#009e73",
  accent: "#56b4e9",
  route: { safest: "#009e73", fastest: "#0072b2", science: "#cc79a7" },
} as const;

/** Icône et libellé de chaque niveau : la couleur n'est jamais le seul indice (ENF-06). */
export const alertLevels: Record<AlertLevel, { color: string; icon: string; label: string }> = {
  info: { color: colors.info, icon: "ⓘ", label: "Information" },
  caution: { color: colors.caution, icon: "▲", label: "Attention" },
  danger: { color: colors.danger, icon: "⛔", label: "Danger" },
};

export function hexToRgb(hex: string): Rgb {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export type Theme = "day" | "night";

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}
