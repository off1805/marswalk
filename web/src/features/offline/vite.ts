/**
 * Greffons Vite du mode hors ligne (F7), branchés par web/vite.config.ts.
 * T00 renvoie une liste vide ; F7 y ajoute sa configuration Workbox (vite-plugin-pwa).
 */
import type { PluginOption } from "vite";

export function offlineVitePlugins(): PluginOption[] {
  return [];
}
