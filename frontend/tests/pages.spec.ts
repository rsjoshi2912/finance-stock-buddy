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
