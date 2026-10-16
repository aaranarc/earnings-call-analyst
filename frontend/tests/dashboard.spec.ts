import { test, expect } from "@playwright/test";
test("workspace persists an idea and its evidence, without mixing examples", async ({
  page,
}) => {
  await page.goto("/research");
  await page.getByRole("button", { name: "New thesis" }).click();
  await page
    .getByLabel("Your thesis", { exact: true })
    .fill("Margins recover after wage pressure");
  await page
    .getByLabel("What evidence would you look for?")
    .fill("Look for margin improvement in the next call.");
  await page.getByRole("button", { name: "Save thesis" }).click();
  await expect(
    page.getByRole("heading", { name: "Margins recover after wage pressure" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "AI pilots are becoming real revenue" }),
  ).toHaveCount(0);
  await page
    .getByRole("button")
    .filter({
      has: page.getByRole("heading", {
        name: "Margins recover after wage pressure",
      }),
    })
    .click();
  await page.getByText("Add evidence and your assessment").click();
  for (const [quarter, note] of [["Q1 FY26", "Earlier call: improvement expected. Source: my reviewed notes."], ["Q2 FY26", "Later call: improvement reported. Source: my reviewed notes."]]) {
    await page.getByLabel("Evidence period").fill(quarter);
    await page.getByLabel("Evidence note", {exact: true}).fill(note);
    await page.getByRole("button", {name: "Add timeline entry"}).click();
  }
  await page.getByLabel("Your assessment").selectOption("Supports thesis");
  await page
    .getByLabel("Research note")
    .fill("Check comparable accounting basis.");
  await page
    .getByRole("button", { name: "Mark reviewed", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Margins recover after wage pressure" }),
  ).toBeVisible();
  await expect(page.getByText("Reviewed", { exact: true })).toBeVisible();
  await page.getByLabel("Search theses").fill("nothing matches");
  await expect(
    page.getByRole("heading", { name: "No matching theses" }),
  ).toBeVisible();
});
test("all pages fit a 375px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const path of ["/", "/growth-payoff", "/watchlist", "/research", "/ask", "/eval", "/how-it-works"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
    expect(layout.scroll,`${path}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(layout.width);
  }
  await page.goto("/research");
  await expect(page.getByRole("heading", {name:"What are you watching for?"})).toBeVisible();
  await page.getByRole("button", {name:"Load example workspace"}).click();
  await page
    .getByRole("button")
    .filter({
      has: page.getByRole("heading", {
        name: "AI pilots are becoming real revenue",
      }),
    })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page
      .getByRole("dialog")
      .evaluate((e) => e.getBoundingClientRect().width),
  ).toBeLessThanOrEqual(375);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("ask handles checked evidence, source drawer, pin, and request failure", async ({
  page,
}) => {
  const data = {
    question: "How was revenue?",
    answer_markdown: "Revenue was 10% higher. [c1]",
    refused: false,
    refusal_reason: null,
    route: { kind: "single", companies: ["TEST"], periods: ["Q1 FY27"] },
    hits: [
      {
        chunk_id: 1,
        symbol: "TEST",
        company: "Test fixture",
        fiscal_label: "Q1 FY27",
        speaker: "Test CFO",
        role: "management",
        section: "qa",
        context: [{position: "before", chunk_id: 99, speaker: "Test analyst", role: "analyst", section: "qa", page: 2, text: "What drove the revenue change?"}],
        page: 2,
        text: "Revenue was 10% higher.",
        source_url: "https://example.com/fixture.pdf",
        scores: { dense: 0.5, fts: 0.1, rrf: 0.03, rerank: 0.9 },
      },
    ],
    citations: [{ n: 1, chunk_id: 1 }],
    numbers: [
      {
        where: "answer",
        raw: "10%",
        start: 12,
        end: 15,
        status: "verified",
        source: { raw: "10%", chunk_id: 1 },
      },
    ],
    comparison_table: null,
    timing_s: { total: 0.2 },
  };
  await page.route("**/api/ask", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: `event: status\ndata: "Working"\n\nevent: answer\ndata: ${JSON.stringify(data)}\n\n`,
    }),
  );
  await page.goto("/ask?q=How%20was%20revenue%3F");
  await expect(
    page.getByText("Revenue was 10%", { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "10%: Value matched — not claim verified" })).toBeVisible();
  await page.getByRole("button", { name: "Open citation 1" }).click();
  await expect(page.getByRole("dialog").getByText("Test CFO")).toBeVisible();
  await expect(page.getByRole("dialog").getByText("Q&A", {exact:true})).toBeVisible();
  await page.getByText("Read surrounding excerpts").click();
  await expect(page.getByText("What drove the revenue change?")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open source PDF" }),
  ).toHaveAttribute("href", "https://example.com/fixture.pdf#page=2");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Pin answer", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Pinned answers" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save evidence to a thesis" }).click();
  await page.getByRole("button", { name: "Save evidence", exact: true }).click();
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("quantrag.theses.v2") || "[]"));
  expect(saved[0].status).toBe("Unresolved");
  expect(saved[0].evidence[0].text).toContain("https://example.com/fixture.pdf");
  expect(saved[0].sample).toBe(false);
  for (let i=0;i<2;i++) {
    await page.getByRole("button", {name:"Save evidence to a thesis"}).click();
    await page.getByRole("dialog").getByRole("combobox", {name:"Thesis", exact:true}).selectOption({label: "How was revenue?"});
    await page.getByRole("button", {name:"Save evidence", exact:true}).click();
  }
  const entries = await page.evaluate(() => JSON.parse(localStorage.getItem("quantrag.theses.v2")!)[0].evidence);
  expect(entries).toHaveLength(3);
  expect(new Set(entries.map((e: {id:string}) => e.id)).size).toBe(3);
  expect(entries[0]).toEqual(saved[0].evidence[0]);
  await page.route("**/api/ask", (route) =>
    route.fulfill({ status: 429, body: "busy" }),
  );
  await page.getByLabel("Your question").fill("Another question");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "analyst is busy" }),
  ).toBeVisible();
});
test("unpublished eval shows development results separately from final metrics", async ({ page }) => {
  await page.route("**/api/eval/latest", (route) =>
    route.fulfill({
      json: {
        status: "pending",
        metrics: [],
        ablations: [],
        failure_cases: [],
        agreement: null,
        last_run: null,
      },
    }),
  );
  await page.goto("/eval");
  await expect(
    page.getByRole("heading", { name: "The benchmark is still being built." }),
  ).toBeVisible();
  await expect(page.getByRole("region", {name:"Development measurements"})).toContainText("Development set, not a final benchmark");
  await expect(page.locator(".method-grid .metric-value")).toHaveCount(0);
});

test("coverage map links only available quarters and chart filters theses", async ({ page }) => {
  await page.route("**/api/companies", route => route.fulfill({json: {
    as_of: "2026-10-15", companies: [
      {symbol: "TCS", name: "Tata Consultancy Services", documents: [{fiscal_label: "Q1 FY27", chunks: 10}]},
      {symbol: "INFY", name: "Infosys", documents: [{fiscal_label: "Q2 FY25", chunks: 12}]},
      {symbol: "EMPTY", name: "Not ingested", documents: []}
    ]
  }}));
  await page.goto("/research");
  const map = page.getByRole("region", {name: "Transcript coverage map"});
  await expect(map.getByText("2 companies · 2 calls")).toBeVisible();
  await expect(map.getByRole("link")).toHaveCount(2);
  await expect(map.getByLabel("No transcript")).toHaveCount(2);
  await expect(map.getByRole("link", {name: "Ask about TCS Q1 FY27"})).toHaveAttribute("href", /Q1%20FY27/);
  await page.getByRole("button", {name: "Load example workspace"}).click();
  await page.getByRole("button", {name: "Filter Challenges thesis"}).click();
  await expect(page.locator(".thesis-card")).toHaveCount(1);
  await expect(page.locator(".thesis-card")).toContainText("Margins recover");
});

test("research brief preserves evidence and prints only the report", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("quantrag.theses.v1", JSON.stringify([{
    id: "brief-test", symbol: "TCS", company: "TCS", title: "Testable margin thesis", description: "",
    before: "Earlier source https://example.com/earlier.pdf", after: "Later source https://example.com/later.pdf",
    beforeQuarter: "Q1 FY26", afterQuarter: "Q2 FY26", note: "Compare the cost basis", reviewed: true,
    status: "Supports thesis", sample: false
  }])));
  await page.goto("/research");
  await page.getByRole("button", {name: "Open research brief"}).click();
  const brief = page.getByRole("dialog", {name: "Research brief"});
  await expect(brief).toContainText("PERSONAL RESEARCH");
  await expect(brief).toContainText("Earlier source https://example.com/earlier.pdf");
  await expect(brief).toContainText("Compare the cost basis");
  await expect(brief).not.toContainText("AI pilots");
  await page.emulateMedia({media: "print"});
  await expect(page.locator(".sidebar")).toBeHidden();
  await expect(brief.getByRole("heading", {name: "The evidence so far."})).toBeVisible();
  await expect(brief.getByRole("button", {name: "Print / Save PDF"})).toBeHidden();
  await page.emulateMedia({media: "screen"});
  await page.keyboard.press("Escape");
  await expect(brief).toHaveCount(0);
});

test("legacy migration preserves both notes and third evidence appends", async ({page}) => {
  await page.addInitScript(() => { if (!localStorage.getItem('quantrag.theses.v1')) localStorage.setItem('quantrag.theses.v1', JSON.stringify([{
    id: 'old', symbol: 'TCS', company: 'TCS', title: 'Existing thesis', description: '', before: 'Original first evidence', after: 'Original second evidence', beforeQuarter: 'Q1 FY26', afterQuarter: 'Q2 FY26', note: '', reviewed: true, status: 'Supports thesis', sample: false
  }])); });
  await page.goto('/research');
  await page.getByRole('button').filter({has: page.getByRole('heading', {name:'Existing thesis'})}).click();
  await expect(page.getByLabel('Evidence timeline')).toContainText('Original first evidence');
  await expect(page.getByLabel('Evidence timeline')).toContainText('Original second evidence');
  await page.getByText('Add evidence and your assessment').click();
  await page.getByLabel('Evidence note', {exact:true}).fill('Third quarter evidence');
  await page.getByRole('button', {name:'Add timeline entry'}).click();
  const stored = await page.evaluate(() => ({old:localStorage.getItem('quantrag.theses.v1'), rows:JSON.parse(localStorage.getItem('quantrag.theses.v2')!)}));
  expect(stored.old).toContain('Original second evidence');
  expect(stored.rows[0].evidence.map((e: {text:string}) => e.text)).toEqual(['Original first evidence','Original second evidence','Third quarter evidence']);
  expect(stored.rows[0].status).toBe('Unresolved');
  expect(stored.rows[0].reviewed).toBe(false);
});

test("workspace imports merge safely, reject invalid data and support export restore", async ({page}) => {
  const row = {id:'import-1',company:'TCS',symbol:'TCS',title:'Restored thesis',description:'',before:'Historic evidence',after:'',beforeQuarter:'Q1 FY26',afterQuarter:'',note:'Preserved note',reviewed:false,status:'Unresolved',sample:false};
  await page.goto('/research');
  const upload = async (data: unknown) => page.getByLabel('Import workspace JSON').setInputFiles({name:'research.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
  await upload({version:1,theses:[row]});
  await page.getByRole('button',{name:'Merge into my workspace'}).click();
  await expect(page.getByRole('heading',{name:'Restored thesis',exact:true})).toBeVisible();
  await upload({version:1,theses:[row]});
  await page.getByRole('button',{name:'Merge into my workspace'}).click();
  await expect(page.locator('.thesis-card')).toHaveCount(1);
  await upload({version:1,theses:[{...row,title:'Conflicting thesis'}]});
  await page.getByRole('button',{name:'Merge into my workspace'}).click();
  await expect(page.locator('.thesis-card')).toHaveCount(2);
  await expect(page.getByRole('heading',{name:'Conflicting thesis (imported copy)'})).toBeVisible();
  await upload({version:2,theses:[{...row,evidence:[{text:'invalid entry'}]}]});
  await expect(page.getByRole('alert').filter({hasText:'Invalid evidence'})).toContainText('Invalid evidence');
  await expect(page.locator('.thesis-card')).toHaveCount(2);
  const download = page.waitForEvent('download');
  await page.getByRole('button',{name:'Export theses'}).click();
  const file = await download;
  const path = await file.path();
  await page.evaluate(() => {localStorage.removeItem('quantrag.theses.v2'); localStorage.removeItem('quantrag.theses.v1');});
  await page.reload();
  await page.getByLabel('Import workspace JSON').setInputFiles(path!);
  await page.getByRole('button',{name:'Merge into my workspace'}).click();
  await expect(page.locator('.thesis-card')).toHaveCount(2);
});

test("thesis suggestions preserve source quotes and require manual assessment", async ({page}) => {
  await page.route('**/api/companies', route => route.fulfill({json:{companies:[{symbol:'TCS',name:'TCS',documents:[{fiscal_label:'Q1 FY27',chunks:1}]}]}}));
  await page.route('**/api/thesis/check', route => route.fulfill({json:{symbol:'TCS',assessment:'Unresolved',automatic_status_change:false,suggestions:[{
    period:'Q1 FY27',relation:'supports',reason:'Wage costs bear on the thesis.',evidence:[{quote:'Margins were 24% after wage increases.',chunk_id:42,symbol:'TCS',period:'Q1 FY27',speaker:'CFO',role:'management',page:3,source_url:'https://example.com/transcript.pdf'}]
  }]}}));
  await page.goto('/research');
  await page.getByRole('button',{name:'New thesis'}).click();
  await page.getByLabel('Your thesis',{exact:true}).fill('Wage costs affect margins');
  await page.getByRole('button',{name:'Save thesis'}).click();
  await page.getByRole('button').filter({has:page.getByRole('heading',{name:'Wage costs affect margins'})}).click();
  await page.getByText('Check against earnings calls').click();
  await expect(page.getByText('Only one call is available.',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Check selected calls'}).click();
  await expect(page.getByText('May support',{exact:true})).toBeVisible();
  await expect(page.getByText('Margins were 24% after wage increases.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Keep quoted evidence'}).click();
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('quantrag.theses.v2')!)[0]);
  expect(saved.status).toBe('Unresolved'); expect(saved.reviewed).toBe(false);
  expect(saved.evidence[0].text).toContain('https://example.com/transcript.pdf');
  expect(saved.evidence[0].text).toContain('AI suggestion for review');
  await expect(page.getByRole('button',{name:'Added to your timeline'})).toBeDisabled();
});

test("API proxy restricts methods, paths, origins and body size", async ({request}) => {
  expect((await request.post('/api/unknown',{data:{}})).status()).toBe(404);
  expect((await request.get('/api/ask')).status()).toBe(404);
  expect((await request.post('/api/ask',{headers:{Origin:'https://unrelated.example'},data:{question:'Test question'}})).status()).toBe(403);
  expect((await request.post('/api/ask',{data:'x'.repeat(17000)})).status()).toBe(413);
});

test("invalid saved research is never overwritten by creating a new thesis", async ({page}) => {
  await page.addInitScript(() => localStorage.setItem('quantrag.theses.v2','corrupt-but-recoverable-by-owner'));
  await page.goto('/research');
  await page.getByRole('button',{name:'New thesis'}).click();
  await page.getByLabel('Your thesis',{exact:true}).fill('New idea');
  await page.getByRole('button',{name:'Save thesis'}).click();
  expect(await page.evaluate(()=>localStorage.getItem('quantrag.theses.v2'))).toBe('corrupt-but-recoverable-by-owner');
  await expect(page.getByRole('dialog')).toBeVisible();
});

test("public coverage and eval are available without a running analyst API", async ({request}) => {
  const coverage = await request.get('/api/companies');
  expect(coverage.status()).toBe(200);
  expect((await coverage.json()).source).toBe('committed ingest snapshot');
  const evaluation = await request.get('/api/eval/latest');
  expect(evaluation.status()).toBe(200);
  expect((await evaluation.json()).status).toBe('pending');
});
