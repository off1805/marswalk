/**
 * Hors ligne (ENF-01, F7) : coupure du réseau pendant l'utilisation, puis réouverture de
 * l'application sans réseau. Le front est servi par `vite preview` (build de production),
 * seul cas où le service worker existe.
 */
import { expect, test } from "@playwright/test";
import { openApp, resetTargets } from "./helpers";

test.beforeAll(async ({ request }) => {
  await resetTargets(request);
});

test("L'indicateur réseau suit la coupure et le retour du réseau", async ({ page, context }) => {
  await openApp(page);
  const badge = page.getByTestId("network-badge");
  await expect(badge).toHaveAccessibleName("Online");
  await context.setOffline(true);
  await expect(badge).toHaveAccessibleName("Offline");
  await expect(badge).toContainText("○"); // pas la couleur seule (ENF-06)
  await context.setOffline(false);
  await expect(badge).toHaveAccessibleName("Online");
});

test("Le plan déjà chargé reste lisible hors ligne", async ({ page, context }) => {
  await openApp(page);
  await expect(page.getByRole("article", { name: /^Variante / })).toHaveCount(3, { timeout: 30_000 });
  await page.getByRole("button", { name: "Select variant Safest" }).click();
  await expect(page.getByRole("region", { name: "Route profile" })).toContainText("Profile · Safest");
  await context.setOffline(true);
  await expect(page.getByTestId("network-badge")).toHaveAccessibleName("Offline");
  // Cibles, variantes, profil et panneau sécurité restent affichés et utilisables
  await page.getByRole("button", { name: "Target Front du delta" }).click();
  await expect(page.getByLabel("Target card: Front du delta")).toBeVisible();
  await expect(page.getByRole("article", { name: "Variante Safest" })).toContainText("Selected");
  await expect(page.getByRole("region", { name: "Route profile" }).getByRole("table", { name: "Segments" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Safety", exact: true })).toContainText(/Reserve on return\s*\d/);
  await context.setOffline(false);
});

test("L'application se rouvre sans réseau", async ({ page, context }) => {
  await openApp(page);
  await expect
    .poll(() => page.evaluate(async () => Boolean((await navigator.serviceWorker.getRegistration())?.active)), {
      timeout: 30_000,
    })
    .toBe(true);
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  // Les réponses de l'API passent par le service worker une fois en ligne : la carte chargée,
  // elles sont en cache pour la réouverture sans réseau.
  await expect(page.getByTestId("map").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator("header").first()).toContainText("Marswalk");
  await expect(page.getByTestId("map").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("network-badge")).toHaveAccessibleName("Offline");
});
