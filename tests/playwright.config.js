import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,           // 2 min per test
  expect: { timeout: 90_000 }, // /api/ask can be slow on cold-start
  reporter: [['list']],
  use: {
    baseURL: 'https://nbo-budget-frontend-1085978218679.us-central1.run.app',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 30_000,
    navigationTimeout: 30_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
