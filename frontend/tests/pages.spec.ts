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
  await expect(page.getByText('Awaiting update', {exact: true})).toBeVisible();
  await expect(page.getByText('Yahoo Finance · May be delayed · 5-minute checks')).toBeVisible();
  await expect(page.getByRole('link', {name: 'ABC announces quarterly results'})).toBeVisible();
  await expect(page.getByText('Moneycontrol · Needs an update')).toBeVisible();
  await expect(page.getByRole('heading', {name: 'No stock calls today'})).toBeVisible();
  await expect(page.locator('.call-row')).toHaveCount(0);
  await page.getByRole('button', {name: 'System health', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'System health', exact: true})).toBeVisible();
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
  await expect(page.locator('.fetch-summary')).toContainText('Fetch complete.');
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
  await expect(page.getByRole('heading', {name: 'Index signals', exact: true})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Try an example'})).toBeHidden();
  await page.locator('.option-calculator > summary').click();
  await page.getByRole('button', {name: 'Try an example'}).click();
  await expect(page.getByText('Exceeds the limit', {exact: true})).toBeVisible();
  await expect(page.getByTestId('option-funding')).toHaveText('₹5,260.00');
  await expect(page.getByTestId('option-stop-loss')).toHaveText('₹710.00');
  await expect(page.getByTestId('option-target')).toHaveText('₹1,240.00');
  await page.locator('.goal-details > summary').click();
  await page.getByLabel('Daily goal to examine').fill('5000');
  await expect(page.getByText('Exceeds the limit', {exact: true})).toBeVisible();
  await expect(page.getByTestId('option-stop-loss')).toHaveText('₹710.00');
  await expect(page.getByTestId('option-funding')).toHaveText('₹5,260.00');
  await expect(page.getByText('50.0% in a day', {exact: true})).toBeVisible();
  await page.getByLabel('Account capital').fill('100000');
  await expect(page.getByText('Within the limit', {exact: true})).toBeVisible();
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
  await expect(nifty.getByText(/Invalidation below/)).toBeVisible();
  await expect(bank.getByText('Skip',{exact:true})).toBeVisible();
  await expect(bank.getByText('This setup has expired. Fetch a new check.')).toBeVisible();
  await expect(page.getByText('Buy put',{exact:true})).toHaveCount(0);
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
  await expect(page.locator('.daily-call-notice')).toContainText('Telegram: delivered');
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

for (const scenario of [{count: 1, buys: 1}, {count: 4, buys: 1}, {count: 10, buys: 0}, {count: 10, buys: 10}]) {
  test(`available ${scenario.count}-call batch with ${scenario.buys} buys stays compact and usable`, async ({page}) => {
    const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
    await page.route('**/api/today', async route => {
      const response = await route.fetch(), data = await response.json();
      const calls = data.calls.slice(0, scenario.count).map((call: Record<string, unknown>, index: number) => ({...call, direction: index < scenario.buys ? 'UP' : 'DOWN', kind: 'stock', allocation: 1000, rank: index + 1}));
      await route.fulfill({json: {...data, calls}});
    });
    await page.goto('./'); await page.getByLabel('Password').fill('pages-browser-fixture-only');
    await page.getByRole('button', {name: 'Open my journal'}).click();
    await expect(page.locator('.call-row')).toHaveCount(scenario.count);
    await expect(page.getByRole('heading', {name: `${scenario.count} ${scenario.count === 1 ? 'call' : 'calls'} · ${scenario.buys} Buy / ${scenario.count - scenario.buys} Sell`, exact: true})).toBeVisible();
    await expect(page.locator('.call-panel')).toHaveCount(scenario.buys === 0 || scenario.buys === scenario.count ? 1 : 2);
    await expect(page.locator('.daily-call-notice')).toHaveCount(0);
    await expect(page.locator('.dataset-label')).toHaveText('Generated sample data');
    await expect(page.locator('.verdict, .sample-note, .fno-card')).toHaveCount(0);
    await expect(page.getByText('Five in each direction. Every one will be scored.')).toHaveCount(0);
    const method = page.getByRole('button', {name: 'Method & data', exact: true});
    await method.click();
    await expect(page.getByRole('dialog')).toContainText('no direction quota');
    await expect(page.getByRole('dialog')).toContainText('uncalibrated');
    await page.keyboard.press('Escape');
    await page.locator('.call-row').first().click();
    await expect(page.getByRole('dialog')).toContainText('Rule score');
    await page.locator('.call-provenance > summary').click();
    await expect(page.getByRole('dialog')).toContainText('Original call saved');
    await page.keyboard.press('Escape');
    await page.screenshot({path: `../data/available-${scenario.count}-${scenario.buys}-desktop.png`, fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: `../data/available-${scenario.count}-${scenario.buys}-mobile.png`, fullPage: true});
    expect(errors).toEqual([]);
  });
}

test('calls precede live feeds and operational details replace inactive warnings', async ({page}) => {
  await page.route('**/api/today', async route => {
    const response = await route.fetch(), data = await response.json();
    await route.fulfill({json: {...data, mode: 'live', daily_status: {status: 'ready', telegram: 'sent'}}});
  });
  await page.route('**/api/quotes', route => route.fulfill({json: {quotes: [], provider: 'Yahoo Finance', refresh_seconds: 300, schedule_known: false, market_open: false}}));
  await page.route('**/api/news', route => route.fulfill({json: {sources: [], articles: []}}));
  await page.goto('./'); await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await expect(page.locator('.call-row')).toHaveCount(10);
  const calls = await page.getByRole('region', {name: 'Daily calls'}).boundingBox();
  const market = await page.getByRole('region', {name: 'Market data'}).boundingBox();
  expect(calls!.y).toBeLessThan(market!.y);
  await expect(page.getByText('Hours unconfirmed', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'System health', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Morning cutoff', exact: true})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Scheduler', exact: true})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'AI helpers', exact: true})).toHaveCount(0);
  await expect(page.getByRole('heading', {name: 'F&O', exact: true})).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Try it', exact: true}).first()).toBeHidden();
  await page.getByText('Method and experiments', {exact: true}).click();
  await expect(page.getByRole('button', {name: 'Try it', exact: true}).first()).toBeVisible();
});

test('partial current-session results use actual resolved counts', async ({page}) => {
  await page.route('**/api/today', async route => {
    const response = await route.fetch(), data = await response.json();
    const calls = data.calls.slice(0, 4).map((call: Record<string, unknown>, index: number) => ({...call, kind: 'stock', allocation: 1000, result: index === 0 ? 'Right' : index === 1 ? 'Wrong' : 'Pending', pnl: index === 0 ? 8.5 : index === 1 ? -11.5 : null, baseline_pnl: index < 2 ? 8.5 : null}));
    const today_summary = {...data.today_summary, days: 1, total: 2, right: 1, wrong: 1, pending: 2, accuracy: 50, baseline_accuracy: 100, pnl: -3, baseline_pnl: 17};
    await route.fulfill({json: {...data, calls, today_summary}});
  });
  await page.goto('./'); await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  const result = page.locator('.metric').filter({hasText: 'Today’s result'});
  await expect(result).toContainText('−₹3.00');
  await expect(result).toContainText('2 calls pending');
  await expect(page.locator('.metric').filter({hasText: 'Calls right'})).toContainText('1 / 2');
  await page.getByText('Today’s results', {exact: true}).click();
  const table = page.locator('details').filter({has: page.getByText('Today’s results', {exact: true})});
  await expect(table.locator('tbody tr')).toHaveCount(4);
  await expect(table.getByText('Pending', {exact: true})).toHaveCount(2);
});

test('an empty journal does not invent results or historical records', async ({page}) => {
  const summary = {days: 0, total: 0, right: 0, wrong: 0, pending: 0, accuracy: null, baseline_accuracy: null, pnl: 0, baseline_pnl: 0, winning_days: 0, losing_days: 0, equity: []};
  await page.route('**/api/today*', async route => {
    const response = await route.fetch(), data = await response.json();
    await route.fulfill({json: {...data, calls: [], yesterday: [], dates: [], previous_date: null, summary, today_summary: summary, yesterday_summary: summary}});
  });
  await page.route('**/api/track-record', route => route.fulfill({json: {summary, months: [], rolling: [], calibration: [], groups: [], causes: []}}));
  await page.goto('./'); await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await expect(page.getByRole('heading', {name: 'No stock calls today'})).toBeVisible();
  await expect(page.locator('.metric').first().locator('strong')).toHaveText('—');
  await expect(page.locator('.previous-results')).toHaveCount(0);
  await page.getByRole('button', {name: 'Calls by day', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'No saved calls yet'})).toBeVisible();
  await page.getByRole('button', {name: 'Track record', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'No completed results yet'})).toBeVisible();
  await expect(page.locator('.performance-strip')).toHaveCount(0);
  await expect(page.locator('.metric').first().locator('strong')).toHaveText('—');
});

test('a failed index recheck suppresses saved direction and option actions', async ({page}) => {
  let offline = false;
  await page.route('**/api/indices', route => {
    if (offline) return route.fulfill({status: 503, json: {detail: 'Fixture connection unavailable'}});
    const now = new Date().toISOString(), validUntil = new Date(Date.now() + 300000).toISOString();
    return route.fulfill({json: {server_time: now, can_fetch: true, option_provider: 'upstox', history: [], limits: {capital: 10000, risk: 100},
      refresh: {status: 'idle', busy: false, retry_after_seconds: 0, message: ''}, indices: [{symbol: 'NIFTY', name: 'Nifty 50', price: 21070, direction: 'UP', reason: 'Fixture setup', assessed_at: now, candle_at: now, valid_until: validUntil, option: {action: 'BUY_CALL', reason: 'Fixture quote passed', valid_until: validUntil}}]}});
  });
  await page.route('**/api/indices/refresh', route => {offline = true; return route.fulfill({status: 202, json: {status: 'queued'}});});
  await page.goto('./'); await page.getByLabel('Password').fill('pages-browser-fixture-only');
  await page.getByRole('button', {name: 'Open my journal'}).click();
  await page.getByRole('button', {name: 'Index lab', exact: true}).click();
  await expect(page.getByText('Up bias', {exact: true})).toBeVisible();
  await expect(page.getByText('Buy call', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'Refresh index signals'}).click();
  await expect(page.getByRole('alert')).toContainText('Actions paused.');
  await expect(page.getByText('Up bias', {exact: true})).toHaveCount(0);
  await expect(page.getByText('Buy call', {exact: true})).toHaveCount(0);
  await expect(page.getByText('Skip option', {exact: true})).toBeVisible();
});
