import { describe, expect, it } from "vitest";
import openapi from "@contracts/openapi.json";
import { handlers } from "./handlers";

/** Chemin OpenAPI vers motif MSW : {site_id} devient :param. */
const toMsw = (path: string) => path.replace(/\{[^}]+\}/g, ":p");
const norm = (path: string) => path.replace(/:[A-Za-z_]+/g, ":p");

describe("faux serveur", () => {
  it("couvre chaque route de l'API (hors tuiles, servies par Vite)", () => {
    const mocked = new Set(
      handlers
        .map((h) => ((h as { info?: { method?: string; path?: unknown } }).info ?? {}))
        .filter((i) => typeof i.path === "string" && i.method)
        .map((i) => `${String(i.method).toLowerCase()} ${norm(String(i.path))}`),
    );
    const missing: string[] = [];
    for (const [path, ops] of Object.entries(openapi.paths)) {
      if (path.startsWith("/tiles") || path.startsWith("/api/_contracts")) continue;
      for (const method of Object.keys(ops)) {
        const key = `${method} ${toMsw(path)}`;
        if (!mocked.has(key)) missing.push(key);
      }
    }
    expect(missing).toEqual([]);
  });
});
