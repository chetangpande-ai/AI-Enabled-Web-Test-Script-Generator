import { test, expect } from '../fixtures/test-data.fixture';

test.describe('Generated web flow example', () => {
  test('user signs in and reaches an authenticated page', async ({ page, testData }) => {
    await page.goto(process.env.APP_URL ?? 'data:text/html,<main>example</main>');
    await expect(page).not.toHaveURL('about:blank');

    // Example only. Run the agent with a real URL and flow to replace this file.
    const body = page.locator('body');
    // Backup locators: page.getByRole('main'); page.getByText(/example/i)
    await expect(body).toBeVisible();

    void testData;
  });
});
