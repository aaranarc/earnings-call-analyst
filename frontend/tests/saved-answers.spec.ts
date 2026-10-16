import { test, expect } from "@playwright/test";

test("exhausted provider shows dated real examples, never as a live answer, and retries", async ({
  page,
}) => {
  let calls = 0;
  await page.route("**/api/ask", (route) => {
    calls++;
    return route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'event: error\ndata: "The AI provider is busy or temporarily unavailable. Please try again shortly."\n\n',
    });
  });
  await page.goto(
    "/ask?q=What%20was%20TCS%20operating%20margin%20in%20Q1%20FY27%3F",
  );
  const examples = page.getByRole("region", { name: "Saved example answers" });
  await expect(examples).toBeVisible();
  await expect(examples.getByText(/Example answer, saved/)).toHaveCount(3);
  await expect(examples).toContainText("not a live response");
  await expect(examples).toContainText("24%");
  await expect(examples).toContainText("21%");
  await expect(examples).toContainText("2,706");
  await examples.getByText("View cited evidence").first().click();
  await expect(
    examples.getByRole("link", { name: "Open source PDF" }).first(),
  ).toHaveAttribute("href", /^https:\/\/.+#page=/);
  await expect(page.getByText("QuantRAG analyst", { exact: true })).toHaveCount(
    0,
  );
  await page
    .getByRole("button", { name: "Retry question", exact: true })
    .click();
  await expect.poll(() => calls).toBe(2);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(examples).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
});

test("fresh request explains cold start while waiting for the API", async ({
  page,
}) => {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/ask", async (route) => {
    await pending;
    await route.fulfill({ status: 503, body: "{}" });
  });
  await page.goto("/ask?q=TCS%20margins");
  await expect(page.getByRole("status")).toContainText("Waking the analyst");
  await expect(page.getByRole("status")).toContainText("Free hosting");
  await expect(page.getByRole("status")).toContainText("1s elapsed");
  release();
  await expect(
    page.getByRole("alert").filter({ hasText: "The analyst is starting up" }),
  ).toContainText("starting up or unavailable");
  await expect(
    page.getByRole("region", { name: "Saved example answers" }),
  ).toHaveCount(0);
});
