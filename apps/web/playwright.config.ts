import { defineConfig } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: ['**/workspace.spec.ts', '**/language.spec.ts'],
  outputDir: './dist/test-results',
  reporter: [['list'], ['html', { outputFolder: path.resolve('apps/web/dist/playwright-report'), open: 'never' }]],
  timeout: 30000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', channel: 'msedge', headless: true, viewport: { width: 1366, height: 768 }, trace: 'retain-on-failure' },
  webServer: { command: 'pnpm dev:web', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI, timeout: 60000, cwd: process.cwd() },
});
