/**
 * Automatic accessibility audit (axe-core) on both views — map and 3D — in both themes
 * (ENF-06). WCAG 2.1 A and AA rules.
 *
 * Violations already noted in e2e/ECARTS.md are tolerated one by one (rule and element)
 * and annotated in the report; any other violation fails the test. When a gap is fixed,
 * remove its line from KNOWN.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { openApp, resetTargets } from "./helpers";

// E10 (state color contrast) and E11 (3D view aria-label) are fixed: no tolerated violations.
const KNOWN: { gap: string; rule: string; match: RegExp }[] = [];

async function audit(page: Page, name: string): Promise<string[]> {
  // Wait for CSS transitions to finish (panel transition-colors, 150 ms): right after a theme
  // change, axe would otherwise read a background still in the old theme under text already
  // in the new one (black text on #20262e in daylight mode — intermittent false failure).
  await page.waitForFunction(() => document.getAnimations().every((a) => !(a instanceof CSSTransition) || a.playState !== "running"));
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    // WebGL canvases (map, 3D) have no content inspectable by axe.
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
      if (known) test.info().annotations.push({ type: `gap ${known.gap}`, description: line });
      else unexpected.push(line);
    }
  }
  return unexpected;
}

test.beforeAll(async ({ request }) => {
  await resetTargets(request);
});

// Night mode is the default; the header button switches to full-sun mode.
const THEMES = [
  { name: "night", toggle: null },
  { name: "day", toggle: "Switch to day theme (full sun)" },
] as const;

for (const theme of THEMES) {
  test(`Map, ${theme.name} theme : WCAG 2.1 AA`, async ({ page }) => {
    await openApp(page);
    if (theme.toggle) await page.getByRole("button", { name: theme.toggle }).click();
    await expect(page.getByRole("article", { name: /^Variant / })).toHaveCount(3, { timeout: 30_000 });
    expect(await audit(page, `map-${theme.name}`)).toEqual([]);
  });

  test(`3D view, ${theme.name} theme : WCAG 2.1 AA`, async ({ page }) => {
    await openApp(page);
    if (theme.toggle) await page.getByRole("button", { name: theme.toggle }).click();
    await page.getByRole("link", { name: "3D" }).click();
    await expect(page.getByLabel("3D rendering of the Martian terrain")).toBeVisible({ timeout: 30_000 });
    expect(await audit(page, `3d-${theme.name}`)).toEqual([]);
  });
}
