/**
 * Rejeu de docs/scenario-demo.md sur l'interface web (I2).
 *
 * Une étape du scénario = un test, joués dans l'ordre sur la même page. Une étape que
 * l'application ne permet pas encore est marquée `test.fixme` avec le numéro de son écart
 * dans e2e/ECARTS.md : le reste du scénario continue, et l'écart reste visible dans le
 * rapport. Quand l'écart est corrigé, retirer le `fixme` suffit à le vérifier.
 */
import { expect, test, type Download, type Page } from "@playwright/test";
import { API, SITE, manifest, openApp, resetTargets, screenPoint, targetByName } from "./helpers";

const PLANNED = ["Front du delta", "Unité à olivine", "Bord des dunes"] as const;
const DROPPED = "Chaos de blocs";

test.describe.configure({ mode: "serial" });

let page: Page;
let evaId = "";
interface PlanBody {
  target_ids: string[];
  settings: { max_slope_deg: number };
  routes: { variant: string; warnings: string[]; totals: { max_slope_deg: number } }[];
}
let plan: PlanBody;
/** Messages reçus par le WebSocket de la page, avec leur heure d'arrivée. */
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
        /* message non JSON : ignoré */
      }
    });
  });
});

test.afterAll(async ({ request }) => {
  await page?.close();
  await request.post(`${API}/api/scenarios/solar-event/stop`).catch(() => undefined);
  await resetTargets(request);
});

/** Première alerte danger non acquittée due à l'éruption (et non à la pente, par exemple). */
const solarAlert = () =>
  page.locator('[data-level="danger"][data-acknowledged="false"]').filter({ hasText: /solaire/i }).first();
const right = () => page.getByLabel("Panneau cibles et itinéraire");
const safety = () => page.getByRole("region", { name: "Sécurité", exact: true });

test("1. Ouvrir Marswalk sur le site", async () => {
  const tile = page.waitForResponse((r) => r.url().includes(`/tiles/${SITE}/`) && r.status() === 200, {
    timeout: 30_000,
  });
  await openApp(page);
  const header = page.locator("header").first();
  // Nom du site, sol de mission et heure solaire locale
  await expect(header).toContainText(SITE === "fictif" ? "Site fictif" : /Jezero/i);
  await expect(header).toContainText(/Sol \d+ · \d{2}:\d{2}:\d{2} LMST/);
  // Imagerie : la couche de base du paquet est servie en tuiles
  expect((await tile).ok()).toBeTruthy();
  await expect(page.getByLabel("État de l'API")).toContainText("●");
});

test("2. Choisir le préréglage « Sécurité »", async () => {
  const presets = page.getByRole("radiogroup", { name: "Préréglages" });
  await presets.getByRole("radio", { name: "Navigation" }).click();
  await expect(presets.getByRole("radio", { name: "Navigation" })).toBeChecked();
  await presets.getByRole("radio", { name: "Sécurité" }).click();
  await expect(presets.getByRole("radio", { name: "Sécurité" })).toBeChecked();
  for (const layer of ["Pente", "Ruptures de pente", "Obstacles (avec tampon)"]) {
    await expect(page.getByRole("button", { name: `Détails de la couche ${layer}` })).toBeVisible();
    await expect(page.getByLabel(`Opacité de la couche ${layer}`)).toBeVisible();
  }
  // Chaque couche indique sa source, sa résolution et sa date
  await page.getByRole("button", { name: "Détails de la couche Pente" }).click();
  const details = page.getByRole("button", { name: "Détails de la couche Pente" }).locator("xpath=ancestor::div[1]/..");
  await expect(details).toContainText(/SYNTHETIC|HiRISE|CTX|MOLA/);
  await expect(details).toContainText(/\d+(,\d+)?\s*m/); // résolution
  await expect(details).toContainText(/\d{4}-\d{2}-\d{2}|\d{1,2} \w+ \d{4}/); // date
});

test("3. Cliquer sur le bord des dunes", async ({ request }) => {
  test.fixme(true, "Écart E1 : un clic sur la carte n'interroge pas le point (ECARTS.md)");
  const dunes = await targetByName(request, "Bord des dunes");
  const { bbox } = await manifest(request);
  await page.getByRole("button", { name: "Activer l'interrogation" }).click();
  const at = await screenPoint(page, bbox, dunes.position);
  const query = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/sites/${SITE}/query`) &&
      Math.abs(Number(new URL(r.url()).searchParams.get("lon")) - dunes.position[0]) < 0.001,
  );
  await page.mouse.click(at.x, at.y);
  await query;
  const panel = page.getByRole("region", { name: "Interrogation au sol (EF-07)" });
  for (const label of ["Altitude", "Pente", "Classe de sol", "Inertie thermique", "Minéralogie"]) {
    await expect(panel).toContainText(label);
  }
  await expect(panel).toContainText("±");
  await expect(panel).toContainText("Temps de retour estimé");
});

test("4. Afficher les zones dangereuses", async () => {
  const legend = page.getByLabel("Légende des zones de risque");
  await expect(legend).toContainText("⛔ Interdite");
  await expect(legend).toContainText("▲ Pénalisée");
  const hazards = await page.request.get(`${API}/api/sites/${SITE}/hazards`);
  const body = (await hazards.json()) as { features: { properties: { kind: string; cause: string } }[] };
  const kinds = new Set(body.features.map((f) => f.properties.kind));
  expect([...kinds].sort()).toEqual(["forbidden", "penalized"]);
  // La falaise du front du delta et le bord du cratère sont interdits : le seuil de pente
  // interdite les couvre (voir le rapport des écarts pour la cause affichée).
  expect(body.features.some((f) => f.properties.kind === "forbidden" && f.properties.cause === "slope")).toBeTruthy();
});

test("5. Lire l'objectif scientifique", async () => {
  // Chaque cible porte son objectif (S1)
  await right().getByRole("button", { name: "Cible Front du delta" }).click();
  await expect(page.getByLabel("Fiche cible : Front du delta")).toContainText(/Argiles|carbonates/i);
  await page.getByRole("button", { name: "Fermer la fiche" }).click();
});

test("5 bis. Panneau science du site", async () => {
  const science = page.getByRole("region", { name: /science/i });
  await expect(science).toContainText(/delta/i);
  await expect(science).toContainText(/argiles|carbonates/i);
  await expect(science).toContainText(/olivine/i);
});

test("6. Planifier trois cibles", async () => {
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
  // Moins de 5 s entre la modification des cibles et l'affichage des variantes (EF-05)
  const elapsed = Date.now() - t0;
  test.info().annotations.push({ type: "durée du plan", description: `${elapsed} ms` });
  expect(elapsed).toBeLessThan(5_000);
  expect(plan.target_ids).toHaveLength(3);
  for (const name of PLANNED) await expect(right().getByRole("button", { name: `Cible ${name}` })).toBeVisible();
  await expect(right().getByRole("button", { name: `Cible ${DROPPED}` })).toHaveCount(0);
});

test("7. Comparer les variantes", async () => {
  const cards = page.getByRole("article", { name: /^Variante / });
  await expect(cards).toHaveCount(3);
  for (const name of ["Plus sûre", "Plus rapide", "Science"]) {
    const c = page.getByRole("article", { name: `Variante ${name}` });
    await expect(c).toContainText("Distance");
    await expect(c).toContainText("Durée totale");
    // Aucune variante n'est imposée
    await expect(c.getByRole("button", { name: `Choisir la variante ${name}` })).toBeVisible();
  }
  await expect(page.getByText("Choisie", { exact: true })).toHaveCount(0);
  // La raison des détours : au moins une variante explique ses tronçons
  const explanations = page.getByText(/Explication par tronçon/);
  expect(await explanations.count()).toBeGreaterThan(0);
  await explanations.first().click();
  await expect(cards.locator("details[open] li").first()).not.toBeEmpty();
});

test("7 bis. La raison des détours se lit en clair", async () => {
  test.fixme(true, "Écart E6 : les explications listent les termes du coût, pas la raison du détour (ECARTS.md)");
  await expect(page.locator("details[open] li").first()).toContainText(/contourne|évite/i);
});

test("7 ter. Trois tracés différents", async () => {
  test.fixme(true, "Écart E5 : les trois variantes ont le même tracé et les mêmes totaux (ECARTS.md)");
  const totals = await Promise.all(
    ["Plus sûre", "Plus rapide", "Science"].map((n) =>
      page.getByRole("article", { name: `Variante ${n}` }).locator("dl").textContent(),
    ),
  );
  expect(new Set(totals).size).toBe(3);
});

test("7 quater. Aucune variante ne franchit une zone interdite en silence", async () => {
  test.fixme(true, "Écart E4 : sans chemin possible, le tracé coupe la falaise sans avertissement (ECARTS.md)");
  const labels: Record<string, string> = { safest: "Plus sûre", fastest: "Plus rapide", science: "Science" };
  for (const r of plan.routes) {
    if (r.totals.max_slope_deg <= plan.settings.max_slope_deg) continue;
    // Une pente au-delà du seuil interdit n'est admissible que si la variante le dit.
    expect(r.warnings.length, `${r.variant} : pente max ${r.totals.max_slope_deg}° sans avertissement`).toBeGreaterThan(0);
    await expect(page.getByRole("article", { name: `Variante ${labels[r.variant]}` })).toContainText("▲");
  }
});

test("8. Examiner le profil de la variante choisie", async () => {
  await page.getByRole("button", { name: "Choisir la variante Plus sûre" }).click();
  await expect(page.getByRole("article", { name: "Variante Plus sûre" })).toContainText("Choisie");
  const profile = page.getByRole("region", { name: "Profil d'itinéraire" });
  await expect(profile).toContainText("Profil · Plus sûre");
  await expect(profile.getByTestId("profile-totals")).toContainText(/Durée/);
  await expect(profile.getByTestId("profile-totals")).toContainText(/Pente max/);
  await expect(profile.getByTestId("totals-check")).toContainText("conformes");
  await expect(profile.getByRole("table", { name: "Tronçons" }).locator("tbody tr")).toHaveCount(4); // 3 cibles + retour
  // Survoler le profil déplace le repère : la ligne du tronçon survolé s'allume
  const chart = profile.getByLabel("Profil d'altitude et de pente le long de l'itinéraire");
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height / 2);
  await expect(profile.locator("tbody tr[aria-current]")).toHaveCount(1);
  // Et inversement : survoler un tronçon met le profil au même endroit
  await profile.getByTestId("segment-2").hover();
  await expect(profile.getByTestId("segment-2")).toHaveAttribute("aria-current", "true");
  // Réserve au retour et point de non-retour affichés
  await expect(safety()).toContainText(/Réserve au retour\s*\d/);
  await expect(safety()).toContainText(/Point de non-retour\s*à /);
});

test("9. Voir le site en 3D", async () => {
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

test("9 bis. Survol du terrain le long du tracé", async () => {
  await page.getByRole("button", { name: "Lancer le survol" }).click();
  await expect(page.getByRole("button", { name: "Mettre en pause" })).toBeVisible();
  await expect
    .poll(async () => Number(await page.getByRole("progressbar", { name: "Progression du survol" }).getAttribute("aria-valuenow")))
    .toBeGreaterThan(0);
  await page.getByRole("button", { name: "Mettre en pause" }).click();
});

test("9 ter. Retour à la carte", async () => {
  await page.getByRole("link", { name: "Carte" }).click();
  await expect(page).toHaveURL(/\/(\?|$)/);
  await expect(page.getByRole("article", { name: "Variante Plus sûre" })).toContainText("Choisie");
});

test("10. Lancer la sortie et l'astronaute virtuel en accéléré", async () => {
  const s = safety();
  await s.getByRole("combobox", { name: "Scénario" }).selectOption({ label: "Éruption solaire pendant la sortie" });
  await s.getByRole("combobox", { name: "Accélération" }).selectOption("60");
  const started = page.waitForResponse((r) => r.url().endsWith("/api/eva") && r.request().method() === "POST");
  await s.getByRole("button", { name: "Démarrer la sortie simulée" }).click();
  const res = await started;
  expect(res.ok(), await res.text()).toBeTruthy();
  evaId = ((await res.json()) as { id: string }).id;
  await expect(s).toContainText(`Sortie ${evaId} · ● Temps réel`, { timeout: 15_000 });
  // Les consommables, la dose et la position arrivent par WebSocket et se mettent à jour
  await expect(s.locator('[data-gauge="Oxygène"]')).toContainText(/\d+(,\d+)? %/, { timeout: 15_000 });
  await expect(s.locator('[data-gauge="Dose reçue"]')).toContainText(/\d+(,\d+)? µSv/);
  const telemetry = () => frames.filter((f) => f.type === "telemetry").map((f) => f.payload);
  await expect.poll(() => telemetry().length, { timeout: 30_000 }).toBeGreaterThan(2);
  const t = telemetry();
  expect(new Set(t.map((x) => JSON.stringify(x.position))).size, "la position avance").toBeGreaterThan(1);
  expect(Number(t.at(-1)!.distance_done_m)).toBeGreaterThan(Number(t[0]!.distance_done_m));
  expect(Number(t.at(-1)!.dose_usv)).toBeGreaterThan(Number(t[0]!.dose_usv));
  const o2 = (x: Record<string, unknown>) => (x.consumables as { oxygen_pct: number }).oxygen_pct;
  expect(o2(t.at(-1)!)).toBeLessThan(o2(t[0]!));
});

test("11. Signaler un obstacle et noter une observation", async () => {
  test.fixme(true, "Écart E3 : l'interface n'a ni bouton « obstacle » ni saisie d'observation (ECARTS.md)");
  await page.getByRole("button", { name: /Signaler un obstacle/ }).click();
  await page.getByRole("button", { name: /Observation/ }).click();
});

test("12. Éruption solaire simulée", async () => {
  // Le scénario solar-event démarre avec la sortie ; l'alerte danger arrive par WebSocket.
  const alert = solarAlert();
  await expect(alert).toBeVisible({ timeout: 60_000 });
  const shownAt = Date.now();
  await expect(alert).toHaveAttribute("role", "alert");
  await expect(alert).toContainText(/abri|retour/i);
  await expect(alert).toContainText("➜"); // action conseillée
  await expect(alert.getByRole("button", { name: /^Acquitter : / })).toBeVisible();
  // Moins de 1 s entre la réception du message et l'affichage dans le bandeau
  const id = await alert.getAttribute("data-alert-id");
  const received = frames.find((f) => f.type === "alert" && f.payload.id === id);
  expect(received, `alerte ${id} reçue par WebSocket`).toBeTruthy();
  const delay = shownAt - received!.at;
  test.info().annotations.push({ type: "délai d'affichage de l'alerte", description: `${delay} ms` });
  expect(delay).toBeLessThan(1_000);
  // Le débit de dose a monté
  const doses = frames
    .filter((f) => f.type === "conditions")
    .map((f) => Number(f.payload.dose_rate_usv_h))
    .filter(Number.isFinite);
  test.info().annotations.push({ type: "débits de dose reçus (µSv/h)", description: doses.join(", ") });
  expect(doses.length).toBeGreaterThan(0);
  expect(Math.max(...doses)).toBeGreaterThan(doses[0]! * 2);
});

test("13. Acquitter l'alerte dans le bandeau", async () => {
  const alert = solarAlert();
  const id = await alert.getAttribute("data-alert-id");
  await alert.getByRole("button", { name: /^Acquitter : / }).click();
  await expect(page.locator(`[data-alert-id="${id}"]`)).toHaveAttribute("data-acknowledged", "true");
  await expect(page.locator(`[data-alert-id="${id}"]`)).toContainText("✓ Acquittée");
});

test("14. Retour forcé et export du carnet", async () => {
  // L'itinéraire est recalculé vers l'habitat, puis la sortie se termine.
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
  // L'itinéraire a été recalculé vers l'habitat
  const update = frames.find((f) => f.type === "route_updated");
  expect(update, "message route_updated reçu").toBeTruthy();
  expect(String(update!.payload.reason)).toMatch(/retour|habitat/i);
  // Le carnet de terrain s'exporte en GeoJSON
  await page.getByRole("link", { name: "🖶 Carnet complet" }).click();
  await expect(page.getByRole("heading", { name: `Carnet de terrain · ${evaId}` })).toBeVisible();
  const download: Promise<Download> = page.waitForEvent("download");
  await page.getByRole("button", { name: "⤓ GeoJSON" }).click();
  const file = await (await download).path();
  const { readFileSync } = await import("node:fs");
  const geo = JSON.parse(readFileSync(file, "utf-8")) as { type: string; features: unknown[] };
  expect(geo.type).toBe("FeatureCollection");
  expect(geo.features.length).toBeGreaterThan(0);
});

test("14 bis. Une nouvelle sortie après l'éruption avance normalement", async () => {
  test.fixme(true, "Écart E8 : après l'éruption, toute nouvelle sortie se termine aussitôt sans avancer (ECARTS.md)");
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
