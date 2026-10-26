# Contributing to Seasonal Groceries

Thanks for helping! Bug reports, corrections to the seasonal data and new languages are all welcome.

## Reporting bugs

Open an issue with the steps to reproduce, what you expected, what happened, your Home Assistant version, and logs or a screenshot if you have them.

## Correcting the data

The calendar and pesticide levels live in `custom_components/seasonal_groceries/data/produce.json`, with their sources under `credits`. If you find a mistake, point to the source in your pull request. New data needs a source that may be reused, with credit.

## Adding a language

See "Adding a language" in the [README](README.md#adding-a-language).

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Make your change with a test (write the test first).
3. Run the checks below.
4. Open a pull request describing the problem it solves.

## Development setup

```bash
uv sync --group dev
uv run pytest
uv run ruff check . && uv run ruff format --check .
cd custom_components/seasonal_groceries/frontend && npm ci && npm run build
```

The frontend uses Home Assistant's own elements and theme tokens: always set `appearance`, `variant` and `size` on `ha-button`, use `ha-svg-icon` with `@mdi/js`, theme colour variables and `--ha-space-*` spacing, and keep everything RTL-safe.

For manual and browser testing, see "Development" in the README (`dev/` scripts and `e2e/`).
