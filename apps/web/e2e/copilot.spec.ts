import { expect, test } from '@playwright/test';

/**
 * The Copilot, in a browser.
 *
 * **The bug this suite exists for.** On 2026-08-18 the back end streamed a correct refusal, the
 * API test passed, and the page displayed **nothing**: `state: NO_DIAGNOSIS` arrives on every
 * refusal while the structured `no_diagnosis` frame only arrives when a gate actually failed,
 * and the component required both. Tokens streamed in and rendered nowhere. A user saw an empty
 * turn and asked the question twice, which is exactly what an empty turn teaches somebody to do.
 *
 * Nothing in this repository could have caught it. The answer is assembled in the browser after
 * the stream ends, so a test that reads the source or calls the API is looking at the wrong
 * side of the problem. **Every assertion below is about what a person can see.**
 */

/** The one invariant every test depends on: an answer that produced text must show it. */
async function expectAnswerVisible(page: import('@playwright/test').Page) {
  const turn = page.locator('article.turn').last();
  await expect(turn).toBeVisible();
  const answer = turn.locator('.answer');
  await expect(answer).toBeVisible({ timeout: 120_000 });
  const text = (await answer.innerText()).trim();
  expect(text.length, 'the turn rendered an empty answer').toBeGreaterThan(20);
  return turn;
}

test.describe('the conversation', () => {
  test('a plant question answers with no episode chosen', async ({ page }) => {
    await page.goto('/');

    // The claim the starter chips exist to make: none of this needs a selection.
    await expect(page.getByText('Nothing selected')).toBeVisible();

    await page.getByPlaceholder(/Ask about a machine/i).fill('What equipment do we have?');
    await page.getByRole('button', { name: 'Ask' }).click();

    const turn = await expectAnswerVisible(page);
    await expect(turn).toContainText('Chiller 1');
    // Silence is not health, and the answer has to say so rather than imply it.
    await expect(turn).toContainText(/not a statement that they are healthy/i);
  });

  test('a refusal renders as an answer, not as an empty turn', async ({ page }) => {
    await page.goto('/');
    await page
      .getByPlaceholder(/Ask about a machine/i)
      .fill('Can you change the chilled water setpoint?');
    await page.getByRole('button', { name: 'Ask' }).click();

    // The regression: this exact question rendered nothing at all.
    const turn = await expectAnswerVisible(page);

    // A refusal is a correct outcome and must not be dressed as a failure — D-015.
    const refusal = turn.locator('.card.refusal');
    await expect(refusal).toBeVisible();
    await expect(refusal).toContainText(/not a failure/i);
  });

  test('an out-of-scope question is refused, with an episode selected', async ({ page }) => {
    await page.goto('/');

    // Selecting an episode used to admit *every* question — this is the leak that let
    // "what is the capital of France" come back as an answer about chiller 1.
    await page.locator('details.context-picker > summary').click();
    await page.locator('.context-picker .chip').first().click();
    await expect(page.locator('.context-current')).toBeVisible();

    await page.getByPlaceholder(/Ask about a machine/i).fill('What is the capital of France?');
    await page.getByRole('button', { name: 'Ask' }).click();

    const turn = await expectAnswerVisible(page);
    await expect(turn).toContainText(/outside what Synex can answer/i);
    await expect(turn).not.toContainText(/Paris/i);
  });

  test('the working is available under the answer, and closed by default', async ({ page }) => {
    await page.goto('/');
    await page.getByPlaceholder(/Ask about a machine/i).fill('What equipment do we have?');
    await page.getByRole('button', { name: 'Ask' }).click();
    await expectAnswerVisible(page);

    const inspector = page.locator('details.inspector').last();
    await expect(inspector).toBeVisible();
    // Closed: a reader who must fold away the working to reach the next answer stops reading it.
    expect(await inspector.evaluate((el: HTMLDetailsElement) => el.open)).toBe(false);
    await expect(inspector.locator('summary')).toContainText(/How this answer was reached/i);
  });

  test('turns accumulate rather than replacing one another', async ({ page }) => {
    await page.goto('/');
    const composer = page.getByPlaceholder(/Ask about a machine/i);
    const ask = page.getByRole('button', { name: 'Ask' });

    await composer.fill('What equipment do we have?');
    await ask.click();
    await expectAnswerVisible(page);

    await composer.fill('What fault classes can the model report?');
    await ask.click();
    await expect(page.locator('article.turn')).toHaveCount(2, { timeout: 120_000 });

    // Each turn carries the question that produced it — an answer scrolled back to, with its
    // question gone, is the reading failure the transcript exists to prevent.
    await expect(page.locator('.turn-question').first()).toContainText('What equipment');
  });
});

test.describe('work orders', () => {
  test('lists what was raised and says what it deliberately omits', async ({ page }) => {
    await page.goto('/work-orders');

    // Raised and draftable are different facts. A planner reading a list of drafts would
    // schedule against work nobody committed to, so the surface has to say it omits them.
    await expect(page.getByText(/Drafts are not listed here/i)).toBeVisible();

    // Newest first rather than ranked: severity is agreed for one fault class of nine, so
    // ordering by priority would present a ranking the formula cannot produce.
    await expect(page.getByText(/Newest first, not ranked/i)).toBeVisible();
  });
});

test.describe('the shell', () => {
  test('the page announces itself as Graylinx Synex', async ({ page }) => {
    await page.goto('/');
    // The naming law governs what the page announces, and the visual lockup shows the mark plus
    // "Synex" only — so this checks the accessible name rather than what is drawn.
    await expect(page.getByRole('heading', { level: 1 })).toHaveAccessibleName('Graylinx Synex');
  });

  test('nothing scrolls sideways', async ({ page }) => {
    for (const path of ['/', '/workspace', '/case', '/work-orders', '/job', '/admin', '/reports']) {
      await page.goto(path);
      const overflows = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      );
      expect(overflows, `${path} scrolls horizontally`).toBe(false);
    }
  });

  test('every surface in the rail opens', async ({ page }) => {
    await page.goto('/');
    for (const path of ['/workspace', '/case', '/work-orders', '/job', '/supervisor', '/admin', '/reports']) {
      const response = await page.goto(path);
      expect(response?.status(), `${path} did not load`).toBeLessThan(400);
      await expect(page.locator('main.content')).toBeVisible();
    }
  });
});
