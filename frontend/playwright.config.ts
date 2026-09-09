import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./tests',testIgnore:'pages.spec.ts',fullyParallel:false,workers:1,use:{baseURL:process.env.JOURNAL_BASE_URL || 'http://127.0.0.1:8000',channel:'chrome',headless:true,viewport:{width:1440,height:1100}},reporter:'list'});
