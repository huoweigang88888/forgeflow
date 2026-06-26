/**
 * ForgeFlow AI — Playwright E2E Test Configuration.
 *
 * Runs end-to-end tests against a live API server and Next.js frontend.
 *
 * Usage:
 *   pnpm test:e2e          # run headless
 *   pnpm test:e2e:ui       # interactive UI mode
 *   pnpm test:e2e:report   # view last run report
 */

import { defineConfig, devices } from "@playwright/test";

const API_PORT = 8001;
const WEB_PORT = 3000;

export default defineConfig({
	testDir: "./e2e",
	timeout: 180_000,
	expect: { timeout: 30_000 },
	retries: process.env.CI ? 1 : 0,
	reporter: [
		["html", { outputFolder: "playwright-report" }],
		["list"],
	],
	use: {
		baseURL: `http://localhost:${WEB_PORT}`,
		trace: "on-first-retry",
		screenshot: "only-on-failure",
		// Bypass system proxy — Playwright browser won't go through proxy
		launchOptions: {
			args: ["--no-proxy-server"],
		},
	},

	// Auto-start both API and Web servers for E2E testing.
	// APP_ENV=development is required — Settings only accepts development|staging|production.
	// Use .venv Python directly (not uv run) to avoid Git Bash path resolution issues.
	//
	// NOTE: webServer is disabled when running servers manually.
	// Start manually:
	//   API:  set APP_ENV=development && f:\AI_Forgeflow\forgeflow\apps\api\.venv\Scripts\python.exe -m uvicorn forgeflow.main:app --host 127.0.0.1 --port 8001
	//   Web:  cd apps\web && pnpm dev
	webServer: [],

	projects: [
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"] },
		},
	],
});
