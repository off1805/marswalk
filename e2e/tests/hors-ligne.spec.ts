/**
 * Offline tests (ENF-01, F7): network cut during use, then reopening the application
 * without network. The front is served by `vite preview` (production build),
 * the only case where the service worker exists.
 */
import { expect, test } from "@playwright/test";
import { openApp, resetTargets } from "./helpers";

test.beforeAll(async ({ request }) => {
  await resetTargets(request);
});

test("Network badge follows the connection cut and restoration", async ({ page, context }) => {
  await openApp(page);
  const badge = page.getByTestId("network-badge");
  await expect(badge).toHaveAccessibleName("En ligne");
  await context.setOffline(true);
  await expect(badge).toHaveAccessibleName("Hors ligne");
  await expect(badge).toContainText("○"); // not color alone (ENF-06)
  await context.setOffline(false);
  await expect(badge).toHaveAccessibleName("En ligne");
});

test("An already-loaded plan remains readable offline", async ({ page, context }) => {
  await openApp(page);
  await expect(page.getByRole("article", { name: /^Variante / })).toHaveCount(3, { timeout: 30_000 });
  await page.getByRole("button", { name: "Choisir la variante Plus sûre" }).click();
  await expect(page.getByRole("region", { name: "Profil d'itinéraire" })).toContainText("Profil · Plus sûre");
  await context.setOffline(true);
  await expect(page.getByTestId("network-badge")).toHaveAccessibleName("Hors ligne");
  // Targets, variants, profile and safety panel remain displayed and usable
  await page.getByRole("button", { name: "Cible Front du delta" }).click();
  await expect(page.getByLabel("Fiche cible : Front du delta")).toBeVisible();
  await expect(page.getByRole("article", { name: "Variante Plus sûre" })).toContainText("Choisie");
  await expect(page.getByRole("region", { name: "Profil d'itinéraire" }).getByRole("table", { name: "Tronçons" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Sécurité", exact: true })).toContainText(/Réserve au retour\s*\d/);
  await context.setOffline(false);
});

test("The application reopens without network", async ({ page, context }) => {
  await openApp(page);
  await expect
    .poll(() => page.evaluate(async () => Boolean((await navigator.serviceWorker.getRegistration())?.active)), {
      timeout: 30_000,
    })
    .toBe(true);
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  // API responses go through the service worker once online: after the map loads,
  // they are cached for offline reopening.
  await expect(page.getByTestId("map").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator("header").first()).toContainText("Marswalk");
  await expect(page.getByTestId("map").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("network-badge")).toHaveAccessibleName("Hors ligne");
});
