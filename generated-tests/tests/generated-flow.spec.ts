import { test, expect } from '@playwright/test';

test.describe('Generated web flow example', () => {
  test('user signs in and reaches an authenticated page', async ({ page }) => {
    const testData = {
      username: process.env.USERNAME ?? 'TODO_USERNAME',
      password: process.env.PASSWORD ?? 'TODO_PASSWORD',
    };

    await page.goto(process.env.APP_URL ?? 'https://example.com');
    await expect(page).not.toHaveURL('about:blank');

    // Example only. Run the agent with a real URL and flow to replace this file.
    const body = page.locator('body');
    // Backup locators: page.getByRole('main'); page.getByText(/example/i)
    await expect(body).toBeVisible();

    void testData;
  });
});

