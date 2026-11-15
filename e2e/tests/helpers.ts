/** Outils partagés des tests de bout en bout (I2). */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const SITE = process.env.E2E_SITE ?? "fictif";
export const API = `http://localhost:${process.env.E2E_API_PORT ?? 8100}`;
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

type LonLat = [number, number];
interface Target {
  id: string;
  name: string;
  kind: string;
  position: LonLat;
  objective?: string | null;
  measurement?: string | null;
  work_time_s?: number;
  priority?: number;
}
interface Manifest {
  bbox: [number, number, number, number];
  habitat: { position: LonLat } | LonLat;
}

/** Cibles de départ du site, telles que l'API les sème au démarrage. */
function seedTargets(): Target[] {
  if (SITE === "fictif") {
    return JSON.parse(readFileSync(resolve(ROOT, "contracts/examples/targets.json"), "utf-8")) as Target[];
  }
  const geo = JSON.parse(
    readFileSync(resolve(ROOT, `config/sites/${SITE}/targets-seed.geojson`), "utf-8"),
  ) as { features: { geometry: { coordinates: LonLat }; properties: Omit<Target, "position"> }[] };
  return geo.features.map((f) => ({ ...f.properties, position: f.geometry.coordinates }));
}

/**
 * Remet les cibles du site dans leur état de départ : l'API garde tout en mémoire, et le
 * scénario supprime une cible. Sans cela, le deuxième passage de `--repeat-each 3` partirait
 * d'un autre état que le premier.
 */
export async function resetTargets(request: APIRequestContext): Promise<void> {
  const seeds = seedTargets();
  const res = await request.get(`${API}/api/sites/${SITE}/targets`);
  expect(res.ok()).toBeTruthy();
  const current = (await res.json()) as Target[];
  const seedNames = new Set(seeds.map((s) => s.name));
  for (const t of current) {
    if (!seedNames.has(t.name)) await request.delete(`${API}/api/targets/${t.id}`);
  }
  const have = new Set(current.map((t) => t.name));
  for (const s of seeds) {
    if (have.has(s.name)) continue;
    const created = await request.post(`${API}/api/sites/${SITE}/targets`, {
      data: {
        name: s.name,
        kind: s.kind,
        position: s.position,
        objective: s.objective ?? null,
        measurement: s.measurement ?? null,
        work_time_s: s.work_time_s ?? 600,
        priority: s.priority ?? 2,
      },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
  }
}

export async function targetByName(request: APIRequestContext, name: string): Promise<Target> {
  const res = await request.get(`${API}/api/sites/${SITE}/targets`);
  const t = ((await res.json()) as Target[]).find((x) => x.name === name);
  if (!t) throw new Error(`Cible absente : ${name}`);
  return t;
}

export async function manifest(request: APIRequestContext): Promise<Manifest> {
  const res = await request.get(`${API}/api/sites/${SITE}`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()) as Manifest;
}

/** Ouvre l'application sur le site joué et attend que la carte soit prête. */
export async function openApp(page: Page, path = "/"): Promise<void> {
  await page.goto(`${path}?site=${SITE}`);
  await expect(page.getByTestId("map").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
}

const mercX = (lon: number) => (lon * Math.PI) / 180;
const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));

/**
 * Position à l'écran d'un point [lon, lat] sur la carte telle qu'elle s'ouvre : MapLibre
 * cadre l'emprise du paquet avec 24 px de marge (MapView), sans zoom ni déplacement depuis.
 */
export async function screenPoint(page: Page, bbox: Manifest["bbox"], [lon, lat]: LonLat) {
  const box = await page.getByTestId("map").boundingBox();
  if (!box) throw new Error("Carte introuvable");
  const [w, s, e, n] = bbox;
  const pad = 24;
  const scale = Math.min((box.width - 2 * pad) / (mercX(e) - mercX(w)), (box.height - 2 * pad) / (mercY(n) - mercY(s)));
  const cx = (mercX(w) + mercX(e)) / 2;
  const cy = (mercY(s) + mercY(n)) / 2;
  return {
    x: box.x + box.width / 2 + (mercX(lon) - cx) * scale,
    y: box.y + box.height / 2 - (mercY(lat) - cy) * scale,
  };
}
