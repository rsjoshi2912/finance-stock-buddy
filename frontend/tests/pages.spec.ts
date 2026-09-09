import { test, expect } from '@playwright/test';

test('hosted prefix, cross-origin sign-in, private export and sign-out', async ({page}) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('./');
  await expect(page.getByRole('heading', {name: 'Your private journal.'})).toBeVisible();
  await expect(page.locator('.call-row')).toHaveCount(0);
  await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await expect(page.locator('.call-row')).toHaveCount(10);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  await page.getByRole('button', {name: 'Calls by day', exact: true}).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Export calls'}).click();
  expect((await download).suggestedFilename()).toBe('nifty-signal-calls.csv');
  await page.getByRole('button', {name: 'Sign out', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Your private journal.'})).toBeVisible();
  expect(errors).toEqual([]);
});

test('live view labels stale quotes and keeps empty calls honest', async ({page}) => {
  await page.route('**/api/today', async route => {
    const response = await route.fetch(); const data = await response.json();
    await route.fulfill({json: {...data, mode: 'live', date: null, calls: []}});
  });
  await page.route('**/api/quotes', route => route.fulfill({json: {
    market_open: false, schedule_known: true, refresh_seconds: 300, provider: 'Yahoo Finance',
    notice: 'Free Yahoo data may be delayed or unavailable.',
    quotes: [{symbol: 'ABC', price: 101, change: 1, market_at: '2026-09-04T10:00:00+00:00', stale: true, provider: 'Yahoo Finance', possibly_delayed: true}],
  }}));
  await page.route('**/api/news', route => route.fulfill({json: {
    sources: [{source: 'ET Markets', status: 'ok'}, {source: 'Moneycontrol', status: 'stale'}],
    articles: [{id: 1, source: 'ET Markets', title: 'ABC announces quarterly results', url: 'https://publisher.example/a', published_at: '2026-09-07T01:00:00+00:00', symbols: ['ABC'], stale: false}],
  }}));
  await page.goto('./');
  await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await expect(page.getByText('Last known price · waiting for an update')).toBeVisible();
  await expect(page.getByText('Yahoo Finance · May be delayed')).toBeVisible();
  await expect(page.getByRole('link', {name: 'ABC announces quarterly results'})).toBeVisible();
  await expect(page.getByText('Moneycontrol · Needs an update')).toBeVisible();
  await expect(page.getByText('Your journal is ready for its first calls')).toBeVisible();
  await expect(page.locator('.call-row')).toHaveCount(0);
  await page.getByRole('button', {name: 'System health', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'A look under the hood.'})).toBeVisible();
});

test('on-demand fetch shows progress and reloads prices and news when finished', async ({page}) => {
  let requests = 0, finished = false, priceReads = 0;
  await page.route('**/api/today', async route => {
    const response = await route.fetch(); const data = await response.json();
    await route.fulfill({json: {...data, mode: 'live', date: null, calls: []}});
  });
  await page.route('**/api/refresh', async route => {
    if (route.request().method() === 'POST') requests++;
    const state = !requests ? {id: null, status: 'idle', busy: false, retry_after_seconds: 0, message: 'Ready.'}
      : !finished ? {id: 'one-fetch', status: 'running', busy: true, retry_after_seconds: 0, message: 'Fetching news…'}
      : {id: 'one-fetch', status: 'complete', busy: false, retry_after_seconds: 60, message: 'Fetch complete.',
          prices: {status: 'ok', detail: 'Checked 1 price.'}, news: {status: 'ok', detail: 'Added 1 article.'}};
    await route.fulfill({json: state});
  });
  await page.route('**/api/quotes', route => {
    priceReads++;
    return route.fulfill({json: {provider: 'Yahoo Finance', refresh_seconds: 300, market_open: true, schedule_known: true,
      quotes: [{symbol: 'ABC', price: finished ? 105 : 101, change: 1, market_at: '2026-09-07T05:00:00+00:00', stale: false}]}});
  });
  await page.route('**/api/news', route => route.fulfill({json: {sources: [], articles: !finished ? [] : [
    {id: 1, title: 'Just-fetched results', source: 'Fixture news', url: 'https://publisher.example/news', published_at: '2026-09-07T05:00:00+00:00', symbols: [], stale: false},
  ]}}));
  await page.goto('./');
  await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await page.getByRole('button', {name: 'Fetch latest', exact: true}).click();
  await expect(page.getByRole('button', {name: 'Fetching…', exact: true})).toBeDisabled();
  await expect(page.getByText('Fetching news…', {exact: true})).toBeVisible();
  await page.reload();
  await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await expect(page.getByRole('button', {name: 'Fetching…', exact: true})).toBeDisabled();
  const before = priceReads;
  finished = true;
  await expect(page.getByText('Fetch complete.', {exact: true})).toBeVisible();
  await expect(page.getByRole('link', {name: 'Just-fetched results'})).toBeVisible();
  await expect(page.locator('.quote-item b')).toHaveText('₹105');
  await expect(page.getByRole('button', {name: 'Fetch latest', exact: true})).toBeDisabled();
  expect(requests).toBe(1); expect(priceReads).toBeGreaterThan(before);
  await expect(page.locator('.call-row')).toHaveCount(0);
});

test('index learning limits, clear examples and formatted Telegram preview', async ({page}) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('./');
  await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await page.getByRole('button', {name: 'Morning note', exact: true}).click();
  await expect(page.locator('.brief-text strong').first()).toContainText('NIFTY SIGNAL');
  await expect(page.locator('.brief-text')).not.toContainText('<b>');
  await page.keyboard.press('Escape');
  await page.getByRole('button', {name: 'Index lab', exact: true}).click();
  await expect(page.getByText('Paper signals · no real orders', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'Try an example'}).click();
  await expect(page.getByText('Skip: one lot exceeds a limit')).toBeVisible();
  await expect(page.getByTestId('option-funding')).toHaveText('₹5,260.00');
  await expect(page.getByTestId('option-stop-loss')).toHaveText('₹710.00');
  await expect(page.getByTestId('option-target')).toHaveText('₹1,240.00');
  await page.getByLabel('Daily goal to examine').fill('5000');
  await expect(page.getByText('Skip: one lot exceeds a limit')).toBeVisible();
  await expect(page.getByText('50.0% in a day', {exact: true})).toBeVisible();
  await page.getByLabel('Account capital').fill('100000');
  await expect(page.getByText('Fits the example limits · paper only')).toBeVisible();
  await page.getByLabel('Units in one lot').fill('');
  await expect(page.getByTestId('option-funding')).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:'../data/index-lab-mobile.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('index research separates direction from options, expires old actions and refreshes on demand', async ({page}) => {
  const errors: string[]=[]; page.on('pageerror', e=>errors.push(e.message));
  let requests=0, readsAfterRefresh=0;
  await page.route('**/api/indices', route=>{
    if(requests) readsAfterRefresh++;
    const busy=requests>0 && readsAfterRefresh===1;
    const now=new Date().toISOString();
    return route.fulfill({json:{can_fetch:true,server_time:now,option_provider:'none',notice:'Fixture research data. Not live market data.',
      limits:{capital:10000,risk:100},history:[],
      refresh:{busy,status:busy?'running':requests?'complete':'idle',message:busy?'Checking Nifty and Bank Nifty…':requests?'Index checks saved.':'',retry_after_seconds:requests&&!busy?60:0},
      indices:[{symbol:'NIFTY',name:'Nifty 50',direction:'UP',reason:'Fixture breakout and retest.',price:21070,
        opening_high:21050,opening_low:21000,trend:'Rising',invalidation:21048,candle_at:now,assessed_at:now,
        valid_until:new Date(Date.now()+300000).toISOString(),option:{action:'SKIP',reason:'Connect an option feed.'}},
        {symbol:'BANKNIFTY',name:'Bank Nifty',direction:'DOWN',reason:'Expired fixture.',price:50000,
        candle_at:now,assessed_at:now,valid_until:'2020-01-01T00:00:00Z',option:{action:'BUY_PUT',reason:'Old candidate.',valid_until:'2020-01-01T00:00:00Z'}}]}});
  });
  await page.route('**/api/indices/refresh', route=>{requests++;return route.fulfill({status:202,json:{status:'queued'}})});
  await page.goto('./');
  await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button',{name:'Open my journal'}).click();
  await page.getByRole('button',{name:'Index lab',exact:true}).click();
  const nifty=page.locator('.index-signal-card').filter({has:page.getByRole('heading',{name:'Nifty 50',exact:true})});
  const bank=page.locator('.index-signal-card').filter({has:page.getByRole('heading',{name:'Bank Nifty',exact:true})});
  await expect(nifty.getByText('Up bias',{exact:true})).toBeVisible();
  await expect(nifty.getByText('Skip option',{exact:true})).toBeVisible();
  await expect(nifty.getByText(/Idea fails below/)).toBeVisible();
  await expect(bank.getByText('Skip',{exact:true})).toBeVisible();
  await expect(bank.getByText('This setup has expired. Fetch a new check.')).toBeVisible();
  await expect(page.getByText('Buy put · paper',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Refresh index signals'}).click();
  await expect(page.getByRole('button',{name:'Checking indices…'})).toBeDisabled();
  await expect(page.locator('.index-fetch-message')).toContainText('Index checks saved.',{timeout:10000});
  await expect(page.getByRole('button',{name:'Refresh index signals'})).toBeDisabled();
  expect(requests).toBe(1);
  await page.getByRole('button',{name:'Preview index Telegram note'}).click();
  await expect(page.locator('.index-note-preview strong').first()).toHaveText('NIFTY SIGNAL · INDEX CHECK');
  await page.screenshot({path:'../data/index-signals-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'../data/index-signals-mobile.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('Today explains skipped calls and shows a no-calls Telegram preview',async({page})=>{
  await page.route('**/api/today',async route=>{
    const response=await route.fetch();const data=await response.json();
    await route.fulfill({json:{...data,mode:'live',date:'2026-09-09',calls:[],daily_status:{status:'skipped',reason:'Only 3 Buy and 17 Sell candidates qualified. The daily batch needs at least 5 of each; no calls were published.',telegram:'sent'}}});
  });
  await page.route('**/api/brief/morning?date=2026-09-09',route=>route.fulfill({json:{html:'<b>NO CALLS TODAY</b>\nOnly 3 Buy and 17 Sell candidates qualified.',text:'NO CALLS TODAY\nOnly 3 Buy and 17 Sell candidates qualified.'}}));
  await page.goto('./');await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button',{name:'Open my journal'}).click();
  await expect(page.getByRole('heading',{name:'No stock calls today'})).toBeVisible();
  await expect(page.locator('.daily-call-notice')).toContainText('3 Buy and 17 Sell');
  await expect(page.locator('.daily-call-notice')).toContainText('Telegram confirmed');
  await expect(page.locator('.call-row')).toHaveCount(0);
  await page.getByRole('button',{name:'Morning note',exact:true}).click();
  await expect(page.locator('.brief-text')).toContainText('NO CALLS TODAY');
  await page.keyboard.press('Escape');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'../data/daily-no-calls-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'See previous calls'}).click();
  await expect(page.getByRole('heading',{name:'10 calls on the record'})).toBeVisible();
});
