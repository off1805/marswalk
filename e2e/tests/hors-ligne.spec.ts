/**
 * Offline tests (ENF-01, F7): network cut during use, then reopening the application
 * without network. The front is served by `vite preview` (production build),
 * the only case where the service worker exists.
 */
import { expect, test } from "@playwright/test";
import { openApp, openProfile, resetTargets } from "./helpers";

test.beforeAll(async ({ request }) => {
  await resetTargets(request);
});

test("Network badge follows the connection cut and restoration", async ({ page, context }) => {
  await openApp(page);
  const badge = page.getByTestId("network-badge");
  await expect(badge).toHaveAccessibleName("Online");
  await context.setOffline(true);
  await expect(badge).toHaveAccessibleName("Offline");
  await expect(badge).toContainText("○"); // pas la couleur seule (ENF-06)
  await context.setOffline(false);
  await expect(badge).toHaveAccessibleName("Online");
});

test("An already-loaded plan remains readable offline", async ({ page, context }) => {
  await openApp(page);
  await expect(page.getByRole("article", { name: /^Variant / })).toHaveCount(3, { timeout: 30_000 });
  await page.getByRole("button", { name: "Select variant Safest" }).click();
  await openProfile(page);
  await expect(page.getByRole("region", { name: "Route profile" })).toContainText("Safest");
  await context.setOffline(true);
  await expect(page.getByTestId("network-badge")).toHaveAccessibleName("Offline");
  // Cibles, variantes, profil et panneau sécurité restent affichés et utilisables
  await page.getByRole("button", { name: "Target Front du delta" }).click();
  await expect(page.getByLabel("Target card: Front du delta")).toBeVisible();
  await expect(page.getByRole("article", { name: "Variant Safest" })).toContainText("Selected");
  await expect(page.getByRole("region", { name: "Route profile" }).getByRole("table", { name: "Segments" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Safety", exact: true })).toContainText(/Reserve on return\s*\d/);
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
  await expect(page.locator("header").first()).toContainText(/marswalk/i);
  await expect(page.getByTestId("map").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("network-badge")).toHaveAccessibleName("Offline");
});
