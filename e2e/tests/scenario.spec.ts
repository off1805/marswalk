/**
 * Replay of docs/scenario-demo.md on the web interface (I2).
 *
 * One scenario step = one test, played in order on the same page. A step that the
 * application does not yet support is marked `test.fixme` with the gap number from
 * e2e/ECARTS.md: the rest of the scenario continues, and the gap remains visible in the
 * report. When a gap is fixed, removing the `fixme` is enough to verify it.
 */
import { expect, test, type Download, type Page } from "@playwright/test";
import { API, SITE, manifest, openApp, resetTargets, screenPoint, targetByName } from "./helpers";

const PLANNED = ["Front du delta", "Unité à olivine", "Bord des dunes"] as const;
const DROPPED = "Chaos de blocs";
const OBSERVATION = "Oblique lamination at the foot of the delta front";

test.describe.configure({ mode: "serial" });

let page: Page;
let evaId = "";
interface PlanBody {
  target_ids: string[];
  settings: { max_slope_deg: number };
  routes: { variant: string; warnings: string[]; totals: { max_slope_deg: number } }[];
}
let plan: PlanBody;
/** WebSocket frames received by the page, with their arrival time. */
const frames: { at: number; type: string; payload: Record<string, unknown> }[] = [];

test.beforeAll(async ({ browser, request }) => {
  await resetTargets(request);
  page = await browser.newPage();
  page.on("websocket", (ws) => {
    ws.on("framereceived", ({ payload }) => {
      try {
        const msg = JSON.parse(String(payload)) as { type: string; payload: Record<string, unknown> };
        frames.push({ at: Date.now(), type: msg.type, payload: msg.payload });
      } catch {
        /* non-JSON message: ignored */
      }
    });
  });
});

test.afterAll(async ({ request }) => {
  await page?.close();
  await request.post(`${API}/api/scenarios/solar-event/stop`).catch(() => undefined);
  await resetTargets(request);
});

/** First unacknowledged danger alert caused by the solar eruption (not by slope, for example). */
const solarAlert = () =>
  page.locator('[data-level="danger"][data-acknowledged="false"]').filter({ hasText: /solaire/i }).first();
const right = () => page.getByLabel("Targets and route panel");
const safety = () => page.getByRole("region", { name: "Safety", exact: true });

test("1. Open Marswalk on the site", async () => {
  const tile = page.waitForResponse((r) => r.url().includes(`/tiles/${SITE}/`) && r.status() === 200, {
    timeout: 30_000,
  });
  await openApp(page);
  const header = page.locator("header").first();
  // Site name, mission sol and local solar time
  await expect(header).toContainText(SITE === "fictif" ? "Site fictif" : /Jezero/i);
  await expect(header).toContainText(/Sol \d+ · \d{2}:\d{2}:\d{2} LMST/);
  // Imagery: the base layer of the package is served as tiles
  expect((await tile).ok()).toBeTruthy();
  await expect(page.getByLabel("API status")).toContainText("●");
});

test("2. Choisir le préréglage « Sécurité »", async () => {
  const presets = page.getByRole("radiogroup", { name: "Presets" });
  await presets.getByRole("radio", { name: "Navigation" }).click();
  await expect(presets.getByRole("radio", { name: "Navigation" })).toBeChecked();
  await presets.getByRole("radio", { name: "Sécurité" }).click();
  await expect(presets.getByRole("radio", { name: "Sécurité" })).toBeChecked();
  for (const layer of ["Pente", "Ruptures de pente", "Obstacles (avec tampon)"]) {
    await expect(page.getByRole("button", { name: `Détails de la couche ${layer}` })).toBeVisible();
    await expect(page.getByLabel(`Opacité de la couche ${layer}`)).toBeVisible();
  }
  // Each layer shows its source, resolution and acquisition date
  await page.getByRole("button", { name: "Détails de la couche Pente" }).click();
  const details = page.getByRole("button", { name: "Détails de la couche Pente" }).locator("xpath=ancestor::div[1]/..");
  await expect(details).toContainText(/SYNTHETIC|HiRISE|CTX|MOLA/);
  await expect(details).toContainText(/\d+(,\d+)?\s*m/); // resolution
  await expect(details).toContainText(/\d{4}-\d{2}-\d{2}|\d{1,2} \w+ \d{4}/); // date
});

test("3. Click on the edge of the dunes", async ({ request }) => {
  const dunes = await targetByName(request, "Bord des dunes");
  const { bbox, habitat: h } = await manifest(request);
  const habitat = Array.isArray(h) ? h : h.position;
  // Before any click, the queried point is the site habitat (not a hard-coded coordinate).
  const atHabitat = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/sites/${SITE}/query`) &&
      Math.abs(Number(new URL(r.url()).searchParams.get("lon")) - habitat[0]) < 1e-6 &&
      Math.abs(Number(new URL(r.url()).searchParams.get("lat")) - habitat[1]) < 1e-6,
  );
  await page.getByRole("button", { name: "Enable query mode" }).click();
  await atHabitat;
  const at = await screenPoint(page, bbox, dunes.position);
  const query = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/sites/${SITE}/query`) &&
      Math.abs(Number(new URL(r.url()).searchParams.get("lon")) - dunes.position[0]) < 0.001,
  );
  await page.mouse.click(at.x, at.y);
  await query;
  const panel = page.getByRole("region", { name: "Ground query (EF-07)" });
  for (const label of ["Altitude", "Pente", "Classe de sol", "Inertie thermique", "Minéralogie"]) {
    await expect(panel).toContainText(label);
  }
  await expect(panel).toContainText("±");
  await expect(panel).toContainText("Estimated return time");
});

test("4. Display hazard zones", async () => {
  const legend = page.getByLabel("Légende des zones de risque");
  await expect(legend).toContainText("⛔ Interdite");
  await expect(legend).toContainText("▲ Pénalisée");
  const hazards = await page.request.get(`${API}/api/sites/${SITE}/hazards`);
  const body = (await hazards.json()) as { features: { properties: { kind: string; cause: string } }[] };
  const kinds = new Set(body.features.map((f) => f.properties.kind));
  expect([...kinds].sort()).toEqual(["forbidden", "penalized"]);
  // The delta front cliff and crater rim are forbidden: the forbidden slope threshold covers them.
  expect(body.features.some((f) => f.properties.kind === "forbidden" && f.properties.cause === "slope")).toBeTruthy();
});

test("5. Read the scientific objective", async () => {
  // Each target carries its objective (S1)
  await right().getByRole("button", { name: "Cible Front du delta" }).click();
  await expect(page.getByLabel("Fiche cible : Front du delta")).toContainText(/Argiles|carbonates/i);
  await page.getByRole("button", { name: "Fermer la fiche" }).click();
});

test("5b. Site science panel", async () => {
  const science = page.getByRole("region", { name: /science/i });
  await expect(science).toContainText(/delta/i);
  await expect(science).toContainText(/argiles|carbonates/i);
  await expect(science).toContainText(/olivine/i);
});

test("6. Plan three targets", async () => {
  await right().getByRole("button", { name: `Cible ${DROPPED}` }).click();
  const card = page.getByLabel(`Fiche cible : ${DROPPED}`);
  const planned = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/api/sites/${SITE}/plans`) &&
      r.request().method() === "POST" &&
      (r.request().postDataJSON() as { target_ids: string[] }).target_ids.length === PLANNED.length,
    { timeout: 30_000 },
  );
  page.once("dialog", (d) => void d.accept());
  await card.getByRole("button", { name: "Supprimer la cible" }).click();
  const t0 = Date.now();
  const res = await planned;
  expect(res.ok()).toBeTruthy();
  plan = (await res.json()) as PlanBody;
  await expect(page.getByRole("article", { name: /^Variante / })).toHaveCount(3);
  // Less than 5 s between target modification and variant display (EF-05)
  const elapsed = Date.now() - t0;
  test.info().annotations.push({ type: "plan computation time", description: `${elapsed} ms` });
  expect(elapsed).toBeLessThan(5_000);
  expect(plan.target_ids).toHaveLength(3);
  for (const name of PLANNED) await expect(right().getByRole("button", { name: `Cible ${name}` })).toBeVisible();
  await expect(right().getByRole("button", { name: `Cible ${DROPPED}` })).toHaveCount(0);
});

test("7. Compare the route variants", async () => {
  const cards = page.getByRole("article", { name: /^Variante / });
  await expect(cards).toHaveCount(3);
  for (const name of ["Plus sûre", "Plus rapide", "Science"]) {
    const c = page.getByRole("article", { name: `Variante ${name}` });
    await expect(c).toContainText("Distance");
    await expect(c).toContainText("Durée totale");
    // No variant is imposed automatically
    await expect(c.getByRole("button", { name: `Choisir la variante ${name}` })).toBeVisible();
  }
  await expect(page.getByText("Choisie", { exact: true })).toHaveCount(0);
  // Detour reason: at least one variant explains its segments
  const explanations = page.getByText(/Explication par tronçon/);
  expect(await explanations.count()).toBeGreaterThan(0);
  await explanations.first().click();
  await expect(cards.locator("details[open] li").first()).not.toBeEmpty();
});

test("7b. Detour reason is in plain language", async () => {
  // One sentence per segment, derived from the deviation from the straight line (gap E6)
  const items = page.locator("details[open] li");
  await expect(items.filter({ hasText: /contourne une pente de \d+°/i }).first()).toBeVisible();
  await expect(items.filter({ hasText: /Tobler|contribution/ })).toHaveCount(0);
});

test("7c. Three different route traces", async () => {
  const totals = await Promise.all(
    ["Plus sûre", "Plus rapide", "Science"].map((n) =>
      page.getByRole("article", { name: `Variante ${n}` }).locator("dl").textContent(),
    ),
  );
  expect(new Set(totals).size).toBe(3);
});

test("7d. No variant silently crosses a forbidden zone", async () => {
  const labels: Record<string, string> = { safest: "Plus sûre", fastest: "Plus rapide", science: "Science" };
  for (const r of plan.routes) {
    if (r.totals.max_slope_deg <= plan.settings.max_slope_deg) continue;
    // A slope beyond the forbidden threshold is only acceptable if the variant says so.
    expect(r.warnings.length, `${r.variant}: max slope ${r.totals.max_slope_deg}° without warning`).toBeGreaterThan(0);
    await expect(page.getByRole("article", { name: `Variante ${labels[r.variant]}` })).toContainText("▲");
  }
});

test("8. Inspect the route profile of the chosen variant", async () => {
  await page.getByRole("button", { name: "Choisir la variante Plus sûre" }).click();
  await expect(page.getByRole("article", { name: "Variante Plus sûre" })).toContainText("Choisie");
  const profile = page.getByRole("region", { name: "Profil d'itinéraire" });
  await expect(profile).toContainText("Profil · Plus sûre");
  await expect(profile.getByTestId("profile-totals")).toContainText(/Durée/);
  await expect(profile.getByTestId("profile-totals")).toContainText(/Pente max/);
  await expect(profile.getByTestId("totals-check")).toContainText("conformes");
  await expect(profile.getByRole("table", { name: "Tronçons" }).locator("tbody tr")).toHaveCount(4); // 3 targets + return
  // Hovering the profile moves the marker: the hovered segment row is highlighted
  const chart = profile.getByLabel("Profil d'altitude et de pente le long de l'itinéraire");
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height / 2);
  await expect(profile.locator("tbody tr[aria-current]")).toHaveCount(1);
  // Conversely: hovering a segment row updates the profile position
  await profile.getByTestId("segment-2").hover();
  await expect(profile.getByTestId("segment-2")).toHaveAttribute("aria-current", "true");
  // Return reserve and point of no return are displayed
  await expect(safety()).toContainText(/Réserve au retour\s*\d/);
  await expect(safety()).toContainText(/Point de non-retour\s*à /);
});

test("9. View the site in 3D", async () => {
  await page.getByRole("link", { name: "3D" }).click();
  await expect(page).toHaveURL(/\/3d/);
  const canvas = page.getByLabel("Rendu 3D du terrain martien");
  await expect(canvas).toBeVisible({ timeout: 30_000 });
  const group = page.getByRole("radiogroup", { name: "Exagération verticale" });
  const options = group.getByRole("radio");
  expect(await options.count()).toBeGreaterThan(1);
  await options.last().click();
  await expect(options.last()).toHaveAttribute("aria-checked", "true");
});

test("9b. Terrain flyover along the route", async () => {
  await page.getByRole("button", { name: "Lancer le survol" }).click();
  await expect(page.getByRole("button", { name: "Mettre en pause" })).toBeVisible();
  await expect
    .poll(async () => Number(await page.getByRole("progressbar", { name: "Progression du survol" }).getAttribute("aria-valuenow")))
    .toBeGreaterThan(0);
  await page.getByRole("button", { name: "Mettre en pause" }).click();
});

test("9c. Return to the map view", async () => {
  await page.getByRole("link", { name: "Carte" }).click();
  await expect(page).toHaveURL(/\/(\?|$)/);
  await expect(page.getByRole("article", { name: "Variante Plus sûre" })).toContainText("Choisie");
});

test("10. Start the EVA and launch the virtual astronaut at high speed", async () => {
  const s = safety();
  await s.getByRole("combobox", { name: "Scénario" }).selectOption({ label: "Éruption solaire pendant la sortie" });
  await s.getByRole("combobox", { name: "Accélération" }).selectOption("60");
  const started = page.waitForResponse((r) => r.url().endsWith("/api/eva") && r.request().method() === "POST");
  await s.getByRole("button", { name: "Démarrer la sortie simulée" }).click();
  const res = await started;
  expect(res.ok(), await res.text()).toBeTruthy();
  evaId = ((await res.json()) as { id: string }).id;
  await expect(s).toContainText(`Sortie ${evaId} · ● Temps réel`, { timeout: 15_000 });
  // Consumables, dose and position arrive via WebSocket and update live
  await expect(s.locator('[data-gauge="Oxygène"]')).toContainText(/\d+(,\d+)? %/, { timeout: 15_000 });
  await expect(s.locator('[data-gauge="Dose reçue"]')).toContainText(/\d+(,\d+)? µSv/);
  const telemetry = () => frames.filter((f) => f.type === "telemetry").map((f) => f.payload);
  await expect.poll(() => telemetry().length, { timeout: 30_000 }).toBeGreaterThan(2);
  const t = telemetry();
  expect(new Set(t.map((x) => JSON.stringify(x.position))).size, "position advances").toBeGreaterThan(1);
  expect(Number(t.at(-1)!.distance_done_m)).toBeGreaterThan(Number(t[0]!.distance_done_m));
  expect(Number(t.at(-1)!.dose_usv)).toBeGreaterThan(Number(t[0]!.dose_usv));
  const o2 = (x: Record<string, unknown>) => (x.consumables as { oxygen_pct: number }).oxygen_pct;
  expect(o2(t.at(-1)!)).toBeLessThan(o2(t[0]!));
});

test("11. Report an obstacle and log an observation", async () => {
  const field = page.getByRole("region", { name: "Relevés de terrain" });
  await expect(field).toBeVisible();
  // Obstacle: reported ahead of the astronaut, the API recalculates the local detour
  const obstacle = page.waitForResponse(
    (r) => r.url().endsWith(`/api/eva/${evaId}/obstacles`) && r.request().method() === "POST",
  );
  await field.getByRole("button", { name: /Signaler un obstacle/ }).click();
  const obstacleRes = await obstacle;
  expect(obstacleRes.ok(), await obstacleRes.text()).toBeTruthy();
  await expect(field.getByRole("status")).toContainText("Obstacle signalé");
  // Observation: a note at the current position, added to the logbook
  await field.getByLabel("Note").fill(OBSERVATION);
  const observation = page.waitForResponse(
    (r) => r.url().endsWith(`/api/eva/${evaId}/observations`) && r.request().method() === "POST",
  );
  await field.getByRole("button", { name: /Noter l'observation/ }).click();
  const observationRes = await observation;
  expect(observationRes.ok(), await observationRes.text()).toBeTruthy();
  await expect(field.getByRole("status")).toContainText("Observation ajoutée au carnet");
});

test("12. Simulated solar eruption", async () => {
  // The solar-event scenario starts with the EVA; the danger alert arrives via WebSocket.
  const alert = solarAlert();
  await expect(alert).toBeVisible({ timeout: 60_000 });
  const shownAt = Date.now();
  await expect(alert).toHaveAttribute("role", "alert");
  await expect(alert).toContainText(/abri|retour/i);
  await expect(alert).toContainText("➜"); // recommended action
  await expect(alert.getByRole("button", { name: /^Acquitter : / })).toBeVisible();
  // Less than 1 s between WebSocket message receipt and banner display
  const id = await alert.getAttribute("data-alert-id");
  const received = frames.find((f) => f.type === "alert" && f.payload.id === id);
  expect(received, `alert ${id} received via WebSocket`).toBeTruthy();
  const delay = shownAt - received!.at;
  test.info().annotations.push({ type: "alert display delay", description: `${delay} ms` });
  expect(delay).toBeLessThan(1_000);
  // Dose rate has increased
  const doses = frames
    .filter((f) => f.type === "conditions")
    .map((f) => Number(f.payload.dose_rate_usv_h))
    .filter(Number.isFinite);
  test.info().annotations.push({ type: "dose rates received (µSv/h)", description: doses.join(", ") });
  expect(doses.length).toBeGreaterThan(0);
  expect(Math.max(...doses)).toBeGreaterThan(doses[0]! * 2);
});

test("13. Acknowledge the alert in the banner", async () => {
  const alert = solarAlert();
  const id = await alert.getAttribute("data-alert-id");
  await alert.getByRole("button", { name: /^Acquitter : / }).click();
  await expect(page.locator(`[data-alert-id="${id}"]`)).toHaveAttribute("data-acknowledged", "true");
  await expect(page.locator(`[data-alert-id="${id}"]`)).toContainText("✓ Acquittée");
});

test("14. Forced return and logbook export", async () => {
  // The route is recalculated toward the habitat, then the EVA ends.
  await expect
    .poll(
      async () => {
        const r = await page.request.get(`${API}/api/eva/${evaId}`);
        return ((await r.json()) as { status: string }).status;
      },
      { timeout: 90_000, intervals: [1_000] },
    )
    .toMatch(/returning|completed|aborted|ended|finished/);
  await expect
    .poll(
      async () => {
        const r = await page.request.get(`${API}/api/eva/${evaId}`);
        return ((await r.json()) as { status: string }).status;
      },
      { timeout: 120_000, intervals: [2_000] },
    )
    .toMatch(/completed|aborted|ended|finished/);
  // The route was recalculated toward the habitat
  // (the first route_updated may be the obstacle detour from step 11)
  const reasons = frames.filter((f) => f.type === "route_updated").map((f) => String(f.payload.reason));
  expect(reasons.length, "route_updated message received").toBeGreaterThan(0);
  expect(reasons.some((r) => /retour|habitat/i.test(r)), reasons.join(" | ")).toBeTruthy();
  // The field logbook exports as GeoJSON
  await page.getByRole("link", { name: "🖶 Carnet complet" }).click();
  await expect(page.getByRole("heading", { name: `Carnet de terrain · ${evaId}` })).toBeVisible();
  const download: Promise<Download> = page.waitForEvent("download");
  await page.getByRole("button", { name: "⤓ GeoJSON" }).click();
  const file = await (await download).path();
  const { readFileSync } = await import("node:fs");
  const geo = JSON.parse(readFileSync(file, "utf-8")) as { type: string; features: unknown[] };
  expect(geo.type).toBe("FeatureCollection");
  expect(geo.features.length).toBeGreaterThan(0);
  // The obstacle and observation from step 11 are in the logbook
  const text = JSON.stringify(geo);
  expect(text).toContain(OBSERVATION);
  expect(text).toMatch(/Obstacle signalé/);
});

test("14b. A new EVA after the eruption progresses normally", async () => {
  await page.request.post(`${API}/api/scenarios/solar-event/stop`);
  const created = await page.request.post(`${API}/api/sites/${SITE}/plans`, {
    data: { target_ids: plan.target_ids, optimize_order: true, variants: ["safest"] },
  });
  const { id: planId } = (await created.json()) as { id: string };
  const eva = await page.request.post(`${API}/api/eva`, { data: { plan_id: planId, route_id: "route-safest", crew: ["EV1"] } });
  const { id } = (await eva.json()) as { id: string };
  await page.request.post(`${API}/api/eva/${id}/simulate`, { data: { speed: 60, scenario_id: null } });
  await expect
    .poll(async () => ((await (await page.request.get(`${API}/api/eva/${id}`)).json()) as { distance_done_m: number }).distance_done_m, {
      timeout: 20_000,
    })
    .toBeGreaterThan(0);
});
