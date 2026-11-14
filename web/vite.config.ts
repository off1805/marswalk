/// <reference types="vitest/config" />
import { createReadStream, existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import { offlineVitePlugins } from "./src/features/offline/vite";

const root = resolve(__dirname, "..");

/** Sert les fichiers du site fictif en mode mock : /tiles/<site>/... et /__fixtures/sites/... */
function serveFixtures(): Plugin {
  const types: Record<string, string> = {
    webp: "image/webp",
    png: "image/png",
    json: "application/json",
    geojson: "application/geo+json",
  };
  return {
    name: "marswalk-fixtures",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0] ?? "";
        let file: string | null = null;
        const tile = /^\/tiles\/([\w-]+)\/(.+)$/.exec(url);
        if (tile) file = resolve(root, "fixtures/sites", tile[1]!, "tiles", tile[2]!);
        const fx = /^\/__fixtures\/(.+)$/.exec(url);
        if (fx) file = resolve(root, "fixtures", fx[1]!);
        if (!file) return next();
        if (!file.startsWith(resolve(root, "fixtures")) || !existsSync(file) || !statSync(file).isFile()) {
          res.statusCode = 404;
          res.end();
          return;
        }
        const ext = file.split(".").pop() ?? "";
        res.setHeader("Content-Type", types[ext] ?? "application/octet-stream");
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const api = process.env.MARSWALK_API_URL ?? "http://localhost:8000";
  const mock = mode === "mock";
  return {
    plugins: [react(), tailwindcss(), ...(mock ? [serveFixtures()] : []), ...offlineVitePlugins()],
    resolve: {
      alias: {
        "@": resolve(__dirname, "src"),
        "@contracts": resolve(root, "contracts"),
      },
    },
    define: {
      "import.meta.env.VITE_MOCK": JSON.stringify(mock ? "1" : ""),
    },
    server: {
      host: true,
      port: 5173,
      fs: { allow: [root] },
      proxy: mock
        ? undefined
        : {
            "/api": api,
            "/tiles": api,
            "/ws": { target: api.replace(/^http/, "ws"), ws: true },
          },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./vitest.setup.ts"],
      css: false,
    },
  };
});
