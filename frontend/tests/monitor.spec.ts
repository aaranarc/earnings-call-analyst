import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('company watchlist preserves favourites and opens literal evidence',async({page})=>{
 await page.goto('/watchlist');
 await expect(page.getByRole('heading',{name:'QuarterLens',exact:true})).toBeVisible();
 const tcs=page.getByRole('button',{name:'Follow Tata Consultancy Services',exact:true});await tcs.click();
 await page.reload();await expect(page.getByRole('button',{name:'Unfollow Tata Consultancy Services'})).toHaveAttribute('aria-pressed','true');
 await page.getByRole('button',{name:'Favourites 1',exact:true}).click();
 await expect(page.locator('.company-tile')).toHaveCount(1);
 await page.getByRole('button',{name:'Open TCS Q2 FY26 operating margin 25.2%'}).click();
 const drawer=page.getByRole('dialog');
 await expect(drawer).toContainText('excluding one-time severance');
 await expect(drawer.getByRole('link',{name:'Open source PDF'})).toHaveAttribute('href',/tcs\.com.*#page=/);
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).exclude('nextjs-portal').analyze()).violations).toEqual([]);
 await page.keyboard.press('Escape');
 await page.locator('.monitor-signal').click();await page.getByRole('button',{name:'Save evidence',exact:true}).click();
 await expect(page.getByRole('button',{name:'Saved to research'})).toBeDisabled();
 await page.getByRole('link',{name:'Open saved research',exact:true}).click();
 await expect(page.locator('.thesis-card').filter({hasText:'Margin down'})).toBeVisible();
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('quantrag.theses.v2')!)[0].status)).toBe('Unresolved');
});
test('missing quarters stay blank and bank results keep their denominator',async({page})=>{
 await page.goto('/watchlist');
 await page.locator('.company-select').filter({hasText:'Infosys'}).click();
 await expect(page.getByLabel('Q3 FY25: no transcript')).toBeVisible();
 await expect(page.getByText('Quarter gaps in the chart.',{exact:false})).toBeVisible();
 await page.locator('.company-select').filter({hasText:'HDFC Bank'}).click();
 await expect(page.getByRole('heading',{name:'Net interest margin',exact:true})).toBeVisible();
 await expect(page.locator('.monitor-metric')).toContainText('3.26%');
 await expect(page.locator('.monitor-metric')).toContainText('On total assets');
 await page.getByRole('button',{name:'Open HDFCBANK Q1 FY27 net interest margin 3.26%'}).click();
 await expect(page.getByRole('dialog')).toContainText('3.40% based on interest earning assets');
 await expect(page.getByRole('dialog')).toContainText('Original issuer financial result');
});

test('all covered quarters remain selectable and a reported range has no invented point',async({page})=>{
 await page.goto('/watchlist');
 await page.locator('.company-select').filter({hasText:'Wipro'}).click();
 await expect(page.getByLabel('Result quarter').locator('option')).toHaveCount(8);
 await page.locator('.company-select').filter({hasText:'Hindustan Unilever'}).click();
 await page.getByLabel('Result quarter').selectOption('Q3 FY25');
 await expect(page.locator('.monitor-metric')).toContainText('23–24%');
 await expect(page.locator('.monitor-metric')).toContainText('no midpoint estimated');
 await page.getByRole('button',{name:'Open Q3 FY25 reported range 23% to 24%'}).click();
 await expect(page.getByRole('dialog')).toContainText('healthy range of 23% to 24%');
});
test('corrupt favourites never overwrite existing saved data',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('quantrag.favourites.v1','corrupt-recoverable-data'));
 await page.goto('/watchlist');
 await expect(page.getByRole('alert').filter({hasText:'Existing data is unchanged'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Follow Tata Consultancy Services',exact:true})).toBeDisabled();
 expect(await page.evaluate(()=>localStorage.getItem('quantrag.favourites.v1'))).toBe('corrupt-recoverable-data');
});

test('follow-through links sourced statements without declaring a fulfilled promise',async({page})=>{
 await page.goto('/watchlist');
 const feature=page.getByRole('region',{name:'Follow-through',exact:true});
 await expect(feature).toContainText('Completion reported');
 await expect(feature).toContainText('24%');
 await expect(feature).toContainText('-130 bps net QoQ');
 await feature.getByRole('button',{name:'Review & save evidence'}).click();
 const drawer=page.getByRole('dialog');
 await expect(drawer).toContainText('effective April 1');
 await expect(drawer).toContainText('completed the annual salary increments');
 await expect(drawer).toContainText('not a verified promise');
 await expect(drawer.getByRole('link',{name:'Open source PDF'})).toHaveCount(3);
 await drawer.getByRole('button',{name:'Save follow-through',exact:true}).click();
 await expect(drawer.getByRole('button',{name:'Saved to research'})).toBeDisabled();
 await page.keyboard.press('Escape');
 await feature.getByRole('button',{name:/Q2 FY26.*Q3 FY26/}).click();
 await expect(feature).toContainText('-50 bps');
 await expect(feature).toContainText('not the net margin change');
 await page.locator('.company-select').filter({hasText:'Infosys'}).click();
 await expect(page.locator('.follow-unavailable')).toContainText('No linked announcement and outcome');
 await page.getByRole('link',{name:'Saved research',exact:true}).first().click();
 await expect(page.locator('.thesis-card').filter({hasText:'Follow-through: Salary increases'})).toBeVisible();
 const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('quantrag.theses.v2')!)[0]);
 expect(saved.status).toBe('Unresolved');expect(saved.evidence).toHaveLength(3);
});
