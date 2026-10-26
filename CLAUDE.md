# CLAUDE.md

## What This Is

Seasonal Groceries: a Home Assistant custom integration (`custom_components/seasonal_groceries`) that knows which Dutch vegetables and fruit are in season (with pesticide levels), optionally ranks Mealie recipes by how seasonal their ingredients are, and ships three Lovelace cards. Distributed via HACS.

## Development

Backend tests: `uv sync --group dev && uv run pytest`. Lint and format: `uv run ruff check . && uv run ruff format --check .` (config in `.ruff.toml`, same as home-upkeep; CI runs it).

Frontend (`custom_components/seasonal_groceries/frontend/`): `npm ci && npm run build` writes into `../www/` (git-ignored).

Local HA: `docker compose -f dev/docker-compose.yml up -d` (http://localhost:8123; Mealie at http://localhost:9925). The integration folder is mounted read-only; restart HA to pick up changes.

## Frontend Design Language

Use HA's native elements and theme tokens, never a custom design system:
- `ha-button`: always set `appearance`, `variant` and `size` (`xs|s|m|l|xl`). Defaults are a big filled brand button. One `filled`/`brand` primary action per view, everything else `plain`/`neutral`, destructive `danger`.
- Icons: `<ha-svg-icon .path=${mdiX}>` with `@mdi/js`, not `ha-icon`.
- Colours: theme variables only (`--primary-text-color`, `--secondary-text-color`, `--success-color`, `--warning-color`, `--error-color`, ...). Spacing: `--ha-space-*`. Mobile first, RTL-safe logical properties.
- Alerts: `ha-alert`. Forms: `ha-form` with selectors. Text inputs: call `stopPropagation()` on `keydown` so HA shortcuts do not fire.
- Cards: `setConfig()` with validation, `.hass`, `getCardSize()`, `getConfigElement()`/`getStubConfig()`, register in `window.customCards`.

## Git

Commits, branches and PRs are authored by `dimac-h` only. No AI attribution in commit messages, PR text or branch names. Open a pull request for each feature; do not merge to `main` directly.
