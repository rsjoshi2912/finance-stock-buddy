import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', testMatch: 'pages.spec.ts', workers: 1,
  use: {baseURL: 'http://127.0.0.1:14173/site/', channel: 'chrome', headless: true}, reporter: 'list',
});
