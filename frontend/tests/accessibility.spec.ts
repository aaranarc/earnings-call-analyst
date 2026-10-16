import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("pages and evidence dialog meet automated WCAG AA checks", async ({
  page,
}) => {
  for (const path of ["/", "/watchlist", "/research", "/ask", "/eval", "/how-it-works"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .exclude("nextjs-portal")
      .analyze();
    expect(
      result.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
      path,
    ).toEqual([]);
  }
  await page.goto("/research");
  await page.getByRole("button", { name: "New thesis" }).click();
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .exclude("nextjs-portal")
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.failureSummary),
    })),
  ).toEqual([]);
});
