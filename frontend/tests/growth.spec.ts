import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { projectPayoff } from "../lib/growth";

test("investment scenario handles ramp, delay, zero and invalid capital", () => {
  const ramp = projectPayoff(
    { capital: 2000, annualReturn: 10, rampYears: 3, startYear: 1 },
    3,
  )!;
  [0, 200 / 3, 400 / 3, 200].forEach((profit, i) =>
    expect(ramp[i].profit).toBeCloseTo(profit, 8),
  );
  expect(
    projectPayoff(
      { capital: 2000, annualReturn: 10, rampYears: 2, startYear: 4 },
      5,
    )?.map((p) => p.profit),
  ).toEqual([0, 0, 0, 0, 100, 200]);
  expect(
    projectPayoff(
      { capital: 2000, annualReturn: 0, rampYears: 1, startYear: 1 },
      3,
    )?.every((p) => p.profit === 0),
  ).toBe(true);
  expect(
    projectPayoff(
      { capital: 2000, annualReturn: -10, rampYears: 1, startYear: 1 },
      3,
    )?.[3].profit,
  ).toBe(-200);
  for (const capital of [0, -1, NaN, Infinity, 1e8])
    expect(
      projectPayoff(
        { capital, annualReturn: 10, rampYears: 1, startYear: 1 },
        5,
      ),
    ).toBeNull();
});

test("Growth Payoff opens sourced milestones and saves original evidence", async ({
  page,
}) => {
  await page.goto("/growth-payoff");
  await expect(
    page.getByRole("heading", { name: "Growth Payoff", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Investment evidence" }),
  ).toContainText("₹2,706 cr");
  await expect(
    page.getByRole("region", { name: "Investment evidence" }),
  ).toContainText("Not established");
  await page
    .getByRole("button", { name: /^3 Q3 FY26 Operating progress/ })
    .click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toContainText("25,000-plus offline stores from 3,000");
  await expect(
    drawer.getByRole("link", { name: "Open source PDF" }),
  ).toHaveAttribute("href", /hul.co.in.*#page=/);
  await drawer.getByRole("button", { name: "Save project evidence" }).click();
  await page.keyboard.press("Escape");
  const rows = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("quantrag.theses.v2")!),
  );
  expect(rows[0].status).toBe("Unresolved");
  expect(rows[0].evidence).toHaveLength(5);
});

test("assumptions change the scenario and never become a company forecast", async ({
  page,
}) => {
  await page.goto("/growth-payoff");
  await page
    .getByRole("button", { name: /HINDUNILVR.*Premium-format capacity/ })
    .click();
  await expect(
    page.getByText("Company forecast unavailable", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Build a scenario" }).click();
  await expect(page.locator(".gp-chart-top strong")).toContainText("₹200 cr");
  await page.getByLabel("Annual operating return", { exact: true }).fill("20");
  await expect(page.locator(".gp-chart-top strong")).toContainText("₹400 cr");
  await page.getByRole("button", { name: "5 years", exact: true }).click();
  await page.getByLabel("First operating year", { exact: true }).fill("5");
  await expect(page.locator(".gp-chart-top strong")).toContainText("₹133.3 cr");
  await page.getByLabel("Scenario capital in crore").fill("0");
  await expect(
    page.getByRole("alert").filter({ hasText: "Enter positive capital" }),
  ).toBeVisible();
  await expect(page.locator(".gp-year-points button")).toHaveCount(0);
  await page.getByLabel("Scenario capital in crore").fill("");
  await expect(page.getByLabel("Scenario capital in crore")).toHaveValue("");
  await expect(page.locator(".gp-year-points button")).toHaveCount(0);
  await page.getByLabel("Scenario capital in crore").fill("1000");
  await expect(page.locator(".gp-chart-top strong")).toContainText("₹66.7 cr");
  await page.getByRole("button", { name: /WIPRO.*HARMAN DTS/ }).click();
  await expect(
    page.getByRole("region", { name: "Investment evidence" }),
  ).toContainText("Not extracted");
  await expect(
    page.getByRole("button", { name: "Build a scenario" }),
  ).toBeVisible();
});

test("project filtering, ceiling basis and source drawer are accessible on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/growth-payoff");
  await page.getByRole("button", { name: "Capacity", exact: true }).click();
  await expect(page.locator(".gp-project")).toHaveCount(2);
  await page
    .getByRole("button", { name: /HCLTECH.*AI infrastructure/ })
    .click();
  await expect(
    page.getByRole("region", { name: "Investment evidence" }),
  ).toContainText("Planned ceiling · up to");
  await page.getByRole("button", { name: "View sources", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "potential to scale to 50 megawatts",
  );
  await expect(page.getByRole("dialog")).toHaveCSS("opacity", "1");
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .exclude("nextjs-portal")
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Build a scenario" }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .exclude("nextjs-portal")
        .analyze()
    ).violations,
  ).toEqual([]);
});
