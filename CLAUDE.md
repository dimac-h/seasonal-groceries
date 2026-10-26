# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Seasonal Groceries: a Home Assistant custom integration (`custom_components/seasonal_groceries`) that knows which Dutch vegetables and fruit are in season (with pesticide levels), optionally ranks Mealie recipes by how seasonal their ingredients are, and ships three Lovelace cards. Distributed via HACS.

## Development

Backend tests: `uv sync --group dev && uv run pytest`. Lint and format: `uv run ruff check . && uv run ruff format --check .` (config in `.ruff.toml`, same as home-upkeep; CI runs it).

Single test: `uv run pytest tests/test_scoring.py::test_name`. Browser tests in `e2e/` are opt-in (`uv run --group e2e pytest e2e`, needs the dev HA below plus `dev/seed_mealie.py` and `dev/setup_ha.py`).

Frontend (`custom_components/seasonal_groceries/frontend/`): `npm ci && npm run build` writes into `../www/` (git-ignored; only `.gitkeep` is tracked, and the Vite config restores it). `npm run typecheck` runs `tsc` alone. HA serves `www/` at `/seasonal_groceries_frontend/`, so the integration loads without a build but the cards do not appear.

Local HA: `docker compose -f dev/docker-compose.yml up -d` (http://localhost:8123; Mealie at http://localhost:9925). The integration folder is mounted read-only; restart HA to pick up changes.

## Architecture

Data flow: bundled dataset + Mealie recipes → `SeasonalGroceriesCoordinator` → WebSocket API → Lit cards.

- `dataset.py` loads `data/produce.json` (calendar months, pesticide residues, cutoffs, credits) into a per-`Language` `Dataset`. Item names and aliases are per language (`names.<code>`, `aliases.<code>`); `const.Language` is the only place languages are listed, and `tests/test_translations.py` fails if an item lacks a name.
- `mealie.py` is the REST client. It can reuse the credentials of HA's own Mealie integration (`MODE_INTEGRATION`), take a manual host/token, or be off (`MODE_NONE`); the seasonal data works without Mealie.
- `matching.py` maps an ingredient to a dataset item (exact, plural suffix, alias, fuzzy ≥ `FUZZY_THRESHOLD`); `scoring.py` resolves each ingredient (applying user corrections) and scores and ranks recipes. Both are pure functions.
- `corrections.py` persists user decisions (confirm/wrong/change/ignore/no_season) in an HA `Store`, keyed by Mealie food or normalised text (`ingredient_key`).
- `coordinator.py` ties it together: polls every 30 min, builds `CoordinatorData` (ranked recipes plus the review queue of unconfirmed matches), recomputes on corrections and at midnight (month rollover), and can write confirmed corrections back to Mealie as aliases. A Mealie outage must not fail setup; the seasonal part keeps working.
- `websocket_api.py` registers `seasonal_groceries/*` commands once in `async_setup`. The cards' `subscribe` command also keeps the coordinator polling while a dashboard is open. Commands are available to non-admins except `review_resolve`.
- `__init__.py` registers the static path and `add_extra_js_url` so one bundle (`frontend/src/main.ts`, which registers all three cards) loads on every dashboard.
- Frontend: `base-card.ts`/`base-editor.ts` hold shared card logic, `api.ts` wraps the WebSocket commands, `i18n.ts` loads `frontend/src/translations/<lang>.json` (separate from `translations/*.json` for HA's setup screens; `strings.json` is the source for the latter). `register.ts` delays registration until `home-assistant` is defined, which works around a load-order race; see `FUTURE_WORK.md` before touching it.

## Frontend Design Language

Use HA's native elements and theme tokens, never a custom design system:
- `ha-button`: always set `appearance`, `variant` and `size` (`xs|s|m|l|xl`). Defaults are a big filled brand button. One `filled`/`brand` primary action per view, everything else `plain`/`neutral`, destructive `danger`.
- Icons: `<ha-svg-icon .path=${mdiX}>` with `@mdi/js`, not `ha-icon`.
- Colours: theme variables only (`--primary-text-color`, `--secondary-text-color`, `--success-color`, `--warning-color`, `--error-color`, ...). Spacing: `--ha-space-*`. Mobile first, RTL-safe logical properties.
- Alerts: `ha-alert`. Forms: `ha-form` with selectors. Text inputs: call `stopPropagation()` on `keydown` so HA shortcuts do not fire.
- Cards: `setConfig()` with validation, `.hass`, `getCardSize()`, `getConfigElement()`/`getStubConfig()`, register in `window.customCards`.

## Git

Commits, branches and PRs are authored by `dimac-h` only. No AI attribution in commit messages, PR text or branch names. Open a pull request for each feature; do not merge to `main` directly.
