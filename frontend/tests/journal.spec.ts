import { test, expect } from '@playwright/test';

test('today, frozen call details, and stock lookup',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.getByRole('heading',{name:'Daily overview'})).toBeVisible();
  await expect(page.locator('.dataset-label')).toHaveText('Generated sample data');
  await expect(page.locator('.call-row')).toHaveCount(10);
  await page.locator('.call-row').first().click();await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button',{name:/See every call on/})).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button',{name:'Close details'})).toBeFocused();
  await page.locator('.call-provenance > summary').click();
  await expect(page.getByText('Original call saved. It cannot be edited.')).toBeVisible();
  await page.getByRole('button',{name:/See every call on/}).click();
  await expect(page.getByRole('heading',{name:'Stock research'})).toBeVisible();
  await page.getByRole('textbox',{name:'Find a stock'}).fill('Infosys');
  await page.locator('.search-results button').click();await expect(page.locator('.stock-title h2')).toHaveText('Infosys');
  await expect(page.locator('.recharts-surface').first()).toBeVisible();
  await expect(page.getByRole('heading',{name:'Company news · INFY'})).toBeVisible();
  await expect(page.getByText('No company news collected yet.')).toBeVisible();
  expect(errors).toEqual([]);
});

test('history filters, record charts, health and note previews',async({page})=>{
  await page.goto('/#history');await expect(page.locator('tbody tr')).toHaveCount(10);
  await page.getByRole('button',{name:'Previous trading day'}).click();
  await page.getByRole('checkbox',{name:'Only wrong calls'}).check();
  await expect(page.locator('tbody')).not.toContainText('Pending');
  await page.locator('summary').filter({hasText: /^Morning note$/}).click();
  await expect(page.locator('.brief-text').first()).toContainText('SAMPLE DATA');
  await page.getByRole('button',{name:'Track record',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Cumulative result'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Rule scores vs results'})).toBeHidden();
  await page.getByText('Accuracy and breakdowns',{exact:true}).click();
  await expect(page.getByRole('heading',{name:'Rule scores vs results'})).toBeVisible();
  await expect(page.locator('.recharts-surface')).toHaveCount(3);
  await page.getByRole('button',{name:'System health',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Morning cutoff',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Scheduler',exact:true})).toBeVisible();
  await expect(page.getByText('No company news has been assessed yet')).toBeVisible();
  await expect(page.getByRole('heading',{name:'AI helpers',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Today',exact:true}).click();
  await page.getByRole('button',{name:'Morning note',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('Preview only · not sent');
  await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('desktop and mobile layouts have no page overflow',async({page})=>{
  await page.goto('/');await expect(page.locator('.call-row')).toHaveCount(10);
  await expect(page.locator('.call-price-range').first()).toBeVisible();
  await page.screenshot({path:'../data/screenshot-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Open navigation'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'../data/screenshot-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Open navigation'}).click();
  await page.getByRole('button',{name:'System health',exact:true}).click();
  await expect(page.getByRole('heading',{name:'System health',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  for (const viewport of [{width:1440,height:1100}, {width:390,height:844}]) {
    await page.setViewportSize(viewport);
    for (const [route, title] of [['today','Daily overview'],['record','Track record'],['history','Calls by day'],['stock','Stock research'],['indices','Index lab'],['health','System health']]) {
      await page.goto(`/#${route}`);
      await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
      await expect(page.getByRole('status',{name:'Loading journal'})).toHaveCount(0);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      await page.screenshot({path:`../data/journal-${route}-${viewport.width}.png`,fullPage:true});
    }
  }
});
