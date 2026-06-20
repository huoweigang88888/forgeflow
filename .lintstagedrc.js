/**
 * lint-staged configuration.
 * Only lint files that are staged for commit (speed optimization).
 */
export default {
  "apps/api/**/*.py": [
    "cd apps/api && uv run ruff check --fix",
    "cd apps/api && uv run ruff format",
  ],
  "apps/web/**/*.{ts,tsx}": [
    "cd apps/web && npx @biomejs/biome check --write",
  ],
  "*.{json,md,yaml,yml}": [
    "prettier --write",
  ],
};
