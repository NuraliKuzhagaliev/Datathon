import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: '**/production.spec.ts',
  outputDir: './dist/production-test-results', reporter: 'list', workers: 1,
  use: {baseURL:'http://127.0.0.1:4173',channel:'msedge',headless:true,viewport:{width:1366,height:768}},
  webServer: {command:'pnpm --filter @cashproof/web preview --port 4173',url:'http://127.0.0.1:4173',reuseExistingServer:false,cwd:process.cwd()},
});
