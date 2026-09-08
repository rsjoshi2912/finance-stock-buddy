import { test, expect } from '@playwright/test';

test('today, frozen call details, and stock lookup',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.getByRole('heading',{name:'Good morning, Ravi.'})).toBeVisible();
  await expect(page.locator('.sample-note')).toContainText('generated examples');
  await expect(page.locator('.call-row')).toHaveCount(10);
  await page.locator('.call-row').first().click();await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('Original call saved. It cannot be edited.')).toBeVisible();
  await page.getByRole('button',{name:/See every call on/}).click();
  await expect(page.getByRole('heading',{name:'Get to know a stock.'})).toBeVisible();
  await page.getByRole('textbox',{name:'Find a stock'}).fill('Infosys');
  await page.locator('.search-results button').click();await expect(page.locator('.stock-title h2')).toHaveText('Infosys');
  await expect(page.locator('.recharts-surface').first()).toBeVisible();
  await expect(page.getByRole('heading',{name:/What the news says about INFY/})).toBeVisible();
  await expect(page.getByText('No collected news has named this company yet.')).toBeVisible();
  expect(errors).toEqual([]);
});

test('history filters, record charts, health and note previews',async({page})=>{
  await page.goto('/#history');await expect(page.locator('tbody tr')).toHaveCount(10);
  await page.getByRole('button',{name:'Previous trading day'}).click();
  await page.getByRole('checkbox',{name:'Only wrong calls'}).check();
  await expect(page.locator('tbody')).not.toContainText('Pending');
  await expect(page.locator('.brief-text').first()).toContainText('SAMPLE DATA');
  await page.getByRole('button',{name:'Track record',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Is its confidence honest?'})).toBeVisible();
  await expect(page.locator('.recharts-surface')).toHaveCount(2);
  await page.getByRole('button',{name:'System health',exact:true}).click();
  await expect(page.locator('.health-card')).toHaveCount(11);
  await expect(page.getByText('No company news has been assessed yet')).toBeVisible();
  await expect(page.getByText('Not connected. The local trend rule still works.')).toBeVisible();
  await page.getByRole('button',{name:'Today',exact:true}).click();
  await page.getByRole('button',{name:'Morning note',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('does not send a Telegram message');
  await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('desktop and mobile layouts have no page overflow',async({page})=>{
  await page.goto('/');await expect(page.locator('.call-row')).toHaveCount(10);
  await page.waitForFunction(()=>(document.querySelector('.recharts-area-curve')?.getAttribute('d')?.length ?? 0) > 500);
  await page.screenshot({path:'../data/screenshot-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Open navigation'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'../data/screenshot-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Open navigation'}).click();
  await page.getByRole('button',{name:'System health',exact:true}).click();
  await expect(page.getByRole('heading',{name:'A look under the hood.'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
