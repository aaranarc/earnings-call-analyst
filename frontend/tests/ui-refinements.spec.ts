import {test, expect} from '@playwright/test';
import {chartScale} from '../lib/chart-scale';
import {answerBlocks} from '../lib/answer-blocks';
import development from '../lib/development-results.json';

test('scenario axes fit positive, negative and zero results with rounded ticks',()=>{
 for(const values of [[0,90.2,180.4,270.6],[0,-90.2,-180.4,-270.6],[0,0,0]]) {
  const scale=chartScale(values,true);
  expect(scale.ticks.length).toBeGreaterThanOrEqual(4);
  expect(scale.ticks.length).toBeLessThanOrEqual(5);
  expect(scale.min).toBeLessThanOrEqual(Math.min(...values));
  expect(scale.max).toBeGreaterThanOrEqual(Math.max(...values));
  if(values.every(v=>v>=0)) expect(scale.min).toBe(0);
 }
 expect(chartScale([0,270.6],true).max).toBe(300);
});
test('markdown list parsing preserves original Unicode numeric offsets',()=>{
 const raw='A summary.\n\n- 📈 Margin was 24% [c1].\n- Revenue grew.\n\n1. Inspect sources.';
 const blocks=answerBlocks(raw);
 expect(blocks.map(b=>b.kind)).toEqual(['p','ul','ol']);
 const item=blocks[1].items[0];
 expect(Array.from(raw).slice(item.start,item.start+Array.from(item.text).length).join('')).toBe(item.text);
 expect(item.text.startsWith('- ')).toBe(false);
});
test('home CTA and development results have honest labels and recorded values',async({page})=>{
 await page.goto('/');
 await expect(page.locator('.hero-actions .button.primary')).toHaveText('Ask the analyst');
 await expect(page.locator('.hero-actions .button.primary')).toHaveAttribute('href','/ask');
 await expect(page.locator('.hero-actions .text-link')).toHaveAttribute('href','/growth-payoff');
 await page.goto('/eval');
 const dev=page.getByRole('region',{name:'Development measurements'});
 await expect(dev).toContainText('Development set, not a final benchmark');
 await expect(dev).toContainText(`${development.memory.retained_min_mb}–${development.memory.retained_max_mb} MB`);
 await expect(dev.locator('tbody tr')).toHaveCount(development.retrieval.length);
});
test('fresh research is empty and examples require an explicit action',async({page})=>{
 await page.goto('/research');
 await expect(page.locator('.thesis-card')).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'What are you watching for?'})).toBeVisible();
 await page.getByRole('button',{name:'Load example workspace'}).click();
 await expect(page.locator('.thesis-card')).toHaveCount(3);
 await expect(page.locator('.mode-strip').getByText('Example workspace',{exact:false})).toBeVisible();
});
test('margin lines keep reported and adjusted separate and pluralise the signal',async({page})=>{
 await page.goto('/watchlist');
 await expect(page.locator('.margin-line-chart')).toBeVisible();
 await expect(page.locator('.margin-line-chart svg g[aria-label="Reported"] circle')).toHaveCount(2);
 await expect(page.locator('.margin-line-chart svg g[aria-label="Adjusted / excludes one-offs"] circle')).toHaveCount(2);
 await expect(page.getByRole('region',{name:'Quarterly review signals'}).getByText('1 signal',{exact:true})).toBeVisible();
});
