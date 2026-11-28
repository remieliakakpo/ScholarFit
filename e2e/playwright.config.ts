import { defineConfig, devices } from "@playwright/test";

// Le site (port 3000) et l'API (port 8000) doivent tourner : start.ps1 / start.sh, ou E2E_BASE_URL vers un site en ligne.
// L'API doit être en PAYMENT_PROVIDER=simulation pour les tests de paiement.
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    locale: "fr-FR",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "ordinateur", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /public\.spec\.ts/ },
  ],
});
