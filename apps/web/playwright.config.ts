import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end configuration.
 *
 * **Why this exists at all.** Every other gate in this repository reads the source or the API.
 * None of them opens the page. A rendering bug found on 2026-08-18 proves the gap: the back end
 * streamed a correct answer, the API test passed, and the surface displayed **nothing** —
 * because `state: NO_DIAGNOSIS` arrives on every refusal while the structured `no_diagnosis`
 * frame only arrives when a gate actually failed, and the component required both. A user saw
 * an empty turn and asked the question twice. No test in the repository could have caught that,
 * because the answer is assembled in the browser after the stream ends.
 *
 * **It reuses the running dev server rather than starting its own.** A second Next.js process
 * would compile into the same `.next` directory the running one owns, which corrupts it — a
 * trap this repository has already hit. `reuseExistingServer` keeps the suite honest about what
 * is actually running, and CI (where nothing is running) starts one.
 */
export default defineConfig({
  testDir: './e2e',
  // Generous: the first request to a route in dev compiles it, and a live turn waits on a 26B
  // model over a tunnel. A tight timeout here would fail the box and blame the page.
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:3100',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // The technician surface is the phone one, and it is the screen a layout bug hurts most.
    { name: 'phone', use: { ...devices['Pixel 5'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:3100',
    reuseExistingServer: true,
    timeout: 180_000,
  },
});
