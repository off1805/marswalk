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

/**
 * Couleurs d'état à employer pour du texte dans le DOM (écart E10). Ce sont des variables
 * CSS qui suivent le thème (tokens.css) : les couleurs vives de `colors` n'atteignent pas
 * 4,5:1 en texte, surtout en thème plein soleil. Pas pour deck.gl ni ECharts (canevas).
 */
export const textColors = {
  info: "var(--text-info)",
  caution: "var(--text-caution)",
  danger: "var(--text-danger)",
  ok: "var(--text-ok)",
} as const;

/** Icône et libellé de chaque niveau : la couleur n'est jamais le seul indice (ENF-06). */
/** `ink` est la couleur du texte posé sur un fond `color` (au moins 4,5:1, écart E10). */
export const alertLevels: Record<AlertLevel, { color: string; ink: string; icon: string; label: string }> = {
  info: { color: colors.info, ink: "#ffffff", icon: "ⓘ", label: "Information" },
  caution: { color: colors.caution, ink: "#000000", icon: "▲", label: "Caution" },
  danger: { color: colors.danger, ink: "#000000", icon: "⛔", label: "Danger" },
};

export function hexToRgb(hex: string): Rgb {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export type Theme = "day" | "night";

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}
