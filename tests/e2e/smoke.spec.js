import { test, expect } from '@playwright/test';

test.describe('Nairobi Budget Agent — live smoke', () => {
  test('landing page renders the hero and feature cards', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /demystified/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /plain language q&a/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /gazette monitor/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /sms digests/i })).toBeVisible();
  });

  test('proxied /health returns ok via the frontend nginx', async ({ request }) => {
    const resp = await request.get('/health');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe('ok');
  });

  test('Q&A: typing a question and clicking Ask AI renders an answer', async ({ page }) => {
    await page.goto('/');
    const input = page.getByPlaceholder(/how much was allocated/i);
    await input.fill('How much was allocated to health in Nairobi?');
    await page.getByRole('button', { name: /ask ai/i }).click();

    // /api/ask hits the agent + Vertex; cold-start can be 30s+.
    const panel = page.locator('.answer-panel');
    await expect(panel).toBeVisible({ timeout: 90_000 });

    // Either we get a real answer or a structured error from the backend.
    const isError = await panel.evaluate((el) => el.classList.contains('error'));
    if (isError) {
      const errText = (await panel.textContent()) ?? '';
      throw new Error(`Backend returned an error response: ${errText.trim()}`);
    }

    const answerText = await page.locator('.answer-text').textContent();
    expect(answerText?.trim().length ?? 0).toBeGreaterThan(20);
  });

  test('subscribe form: shows an error for invalid phone (validates backend wiring)', async ({ page }) => {
    await page.goto('/#digest');
    await page.getByPlaceholder(/\+2547/).fill('not-a-phone');
    await page.getByPlaceholder(/ward/i).fill('Kasarani');
    await page.getByRole('button', { name: /^subscribe/i }).click();

    // The backend rejects non-E.164 phones with a 400; the UI surfaces it as a status line.
    const status = page.locator('.subscribe-status');
    await expect(status).toBeVisible({ timeout: 30_000 });
    await expect(status).toHaveClass(/error/);
  });
});
