/**
 * Contrôle d'accessibilité automatique (axe-core) sur les deux vues, la carte et la 3D, dans
 * les deux thèmes (ENF-06). Règles WCAG 2.1 A et AA.
 *
 * Les violations déjà relevées dans e2e/ECARTS.md sont tolérées une à une (règle et élément),
 * et notées dans le rapport ; toute autre violation fait échouer le test. Quand un écart est
 * corrigé, retirer sa ligne de KNOWN.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { openApp, resetTargets } from "./helpers";

// E10 (contraste des couleurs d'état) et E11 (aria-label de la vue 3D) sont corrigés : plus
// aucune violation tolérée.
const KNOWN: { gap: string; rule: string; match: RegExp }[] = [];

async function audit(page: Page, name: string): Promise<string[]> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    // Les canevas WebGL (carte, 3D) n'ont pas de contenu inspectable par axe.
    .exclude("canvas")
    .analyze();
  await test.info().attach(`axe-${name}.json`, {
    body: JSON.stringify(results.violations, null, 2),
    contentType: "application/json",
  });
  const unexpected: string[] = [];
  for (const v of results.violations) {
    for (const node of v.nodes) {
      const target = node.target.join(" ");
      const line = `${v.id} (${v.impact}) ${target} : ${node.failureSummary?.split("\n")[1]?.trim() ?? v.help}`;
      const known = KNOWN.find((k) => k.rule === v.id && k.match.test(line));
      if (known) test.info().annotations.push({ type: `écart ${known.gap}`, description: line });
      else unexpected.push(line);
    }
  }
  return unexpected;
}

test.beforeAll(async ({ request }) => {
  await resetTargets(request);
});

for (const theme of ["Thème basse lumière", "Thème plein soleil"] as const) {
  test(`Carte, ${theme.toLowerCase()} : WCAG 2.1 AA`, async ({ page }) => {
    await openApp(page);
    await page.getByRole("button", { name: theme }).click();
    await expect(page.getByRole("article", { name: /^Variante / })).toHaveCount(3, { timeout: 30_000 });
    expect(await audit(page, `carte-${theme}`)).toEqual([]);
  });

  test(`Vue 3D, ${theme.toLowerCase()} : WCAG 2.1 AA`, async ({ page }) => {
    await openApp(page);
    await page.getByRole("button", { name: theme }).click();
    await page.getByRole("link", { name: "3D" }).click();
    await expect(page.getByLabel("Rendu 3D du terrain martien")).toBeVisible({ timeout: 30_000 });
    expect(await audit(page, `3d-${theme}`)).toEqual([]);
  });
}
