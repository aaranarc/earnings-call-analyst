import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('company watchlist preserves favourites and opens literal evidence',async({page})=>{
 await page.goto('/watchlist');
 await expect(page.getByRole('heading',{name:'Company watchlist',exact:true})).toBeVisible();
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
 await expect(page.locator('.thesis-card')).toContainText('Margin down');
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('quantrag.theses.v2')!)[0].status)).toBe('Unresolved');
});
test('missing quarters stay blank, single-call companies have no fabricated metric',async({page})=>{
 await page.goto('/watchlist');
 await page.locator('.company-select').filter({hasText:'Infosys'}).click();
 await expect(page.getByLabel('Q3 FY25: no observation')).toBeVisible();
 await expect(page.getByText('Quarter gaps in the chart.',{exact:false})).toBeVisible();
 await page.locator('.company-select').filter({hasText:'HDFC Bank'}).click();
 await expect(page.getByRole('heading',{name:'No margin series available'})).toBeVisible();
 await expect(page.locator('.margin-bar')).toHaveCount(0);
 await expect(page.getByText('No quarterly signal',{exact:true})).toBeVisible();
});
test('corrupt favourites never overwrite existing saved data',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('quantrag.favourites.v1','corrupt-recoverable-data'));
 await page.goto('/watchlist');
 await expect(page.getByRole('alert').filter({hasText:'Existing data is unchanged'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Follow Tata Consultancy Services',exact:true})).toBeDisabled();
 expect(await page.evaluate(()=>localStorage.getItem('quantrag.favourites.v1'))).toBe('corrupt-recoverable-data');
});
