import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./tests/integration', testMatch:'**/*.spec.ts', timeout:120000,
  outputDir:'./dist/integration-test-results', reporter:'list', workers:1,
  use:{channel:'msedge',headless:true,viewport:{width:1366,height:768},trace:'retain-on-failure'},
});
