/**
 * Tests de bout en bout du scénario de démo (I2).
 *
 * Les deux serveurs sont lancés par Playwright :
 *   - l'API FastAPI (uvicorn, sans base : les cibles, plans et sorties vivent en mémoire) ;
 *   - le front construit puis servi par `vite preview`, comme en production
 *     (le service worker hors ligne n'existe qu'au build).
 *
 * Ports dédiés (API 8100, front 4173) pour ne pas croiser `make dev`.
 * Site joué : E2E_SITE (fictif par défaut ; jezero si son paquet est installé).
 */
import { defineConfig, devices } from "@playwright/test";

const API_PORT = Number(process.env.E2E_API_PORT ?? 8100);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 4173);
const CI = Boolean(process.env.CI);
// L'API garde tout en mémoire (cibles, plans, sorties, alertes) : chaque passage part d'une API
// neuve. E2E_REUSE=1 réutilise des serveurs déjà lancés sur ces ports (mise au point).
const REUSE = process.env.E2E_REUSE === "1";
// E2E_SKIP_BUILD=1 sert web/dist tel quel (la CI le construit une fois pour ses trois passages).
const BUILD = process.env.E2E_SKIP_BUILD === "1" ? "" : "pnpm --dir ../web exec vite build && ";

export default defineConfig({
  testDir: "./tests",
  // Une seule API en mémoire partagée : les tests ne tournent pas en parallèle.
  fullyParallel: false,
  workers: 1,
  forbidOnly: CI,
  // Pas de nouvel essai : le critère d'I2 est trois passages de suite, sans rattrapage.
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: CI
    ? [["list"], ["html", { open: "never" }], ["github"]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    viewport: { width: 1600, height: 1000 },
    locale: "fr-FR",
    timezoneId: "UTC",
    acceptDownloads: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1600, height: 1000 },
        // WebGL logiciel : MapLibre, deck.gl et la vue 3D tournent sans GPU dans la CI.
        launchOptions: { args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] },
      },
    },
  ],
  webServer: [
    {
      name: "api",
      command: `uv run --frozen --directory ../api uvicorn marswalk_api.main:app --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/api/health`,
      reuseExistingServer: REUSE,
      timeout: 120_000,
      env: { MARSWALK_WARMUP: "true" },
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      name: "web",
      command: `${BUILD}pnpm --dir ../web exec vite preview --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: REUSE,
      timeout: 240_000,
      env: { MARSWALK_API_URL: `http://localhost:${API_PORT}` },
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
