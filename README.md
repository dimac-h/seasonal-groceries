# Seasonal Groceries

**Seasonal Groceries** shows which Dutch vegetables and fruit are in season this month, how many pesticide residues they carry on average, and, if you use [Mealie](https://mealie.io), which of your recipes are made of the most seasonal produce. Eat what is in season, so your food does not come from glasshouses or travel halfway around the world. Look at it when you plan the week's meals, before you shop.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dimac-h&repository=seasonal-groceries&category=integration)
[![Add Integration to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=seasonal_groceries)

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/dimac-h/seasonal-groceries/main/images/now-card.png" alt="The in-season-now card, showing fruit in season in October with pesticide levels and the most seasonal recipes" width="360"></td>
<td><img src="https://raw.githubusercontent.com/dimac-h/seasonal-groceries/main/images/calendar-card-dark.png" alt="The year calendar card in dark mode" width="360"></td>
</tr>
</table>

## Features

- **In season now:** a list of the vegetables or fruit in season this month, sorted by fewest pesticide residues (unknown last), refreshed on the 1st of the month.
- **Year calendar:** which month each item is in season, with a row limit you choose.
- **Recipe ranking (optional):** your Mealie recipes sorted by the share of their fruit and vegetables that is in season (10 of 10, then 9 of 10, and so on). Nothing is hidden.
- **Match review:** confirm or fix how a Mealie ingredient is matched to a seasonal item. Names and aliases you already have in Mealie are used first, so you rarely need it.
- Dutch and English, light and dark mode, native Home Assistant look.

The seasonal data is for the Netherlands.

## Installation

### HACS / Home Assistant Marketplace (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dimac-h&repository=seasonal-groceries&category=integration)

Search for *Seasonal Groceries*, download it and restart Home Assistant.

### Manual

Download `seasonal_groceries.zip` from the [latest release](https://github.com/dimac-h/seasonal-groceries/releases/latest), unzip it into `custom_components/seasonal_groceries` in your Home Assistant configuration folder and restart. Copying the folder straight from the repository does not work: the built cards are only part of the release zip.

Requires Home Assistant 2026.8.3 or newer.

## Setup

Go to **Settings → Devices & Services → Add Integration**, search for *Seasonal Groceries*, or use the button below.

[![Add Integration to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=seasonal_groceries)

1. **Grocery language** (Nederlands or English). Item names are shown in this language, and your Mealie ingredients are matched against names in this language only. You can change it later in the integration options.
2. **Mealie (optional):** pick one of
   - *Use the existing Home Assistant Mealie integration* (offered when you have one). The URL and token are read from it every time, so a changed token is picked up automatically. Home Assistant's Mealie integration needs Mealie 3.2 or newer.
   - *Enter the Mealie URL and API token.* Create a token in Mealie under your profile settings.
   - *Skip:* you only get the seasonal information, no recipes.

Option **Save corrections as aliases in Mealie**: when you correct a match, the seasonal item's name is also added as an alias to the linked Mealie food, so Mealie knows it from then on.

## Cards

The cards are available in the dashboard card picker. In YAML:

```yaml
type: custom:seasonal-groceries-now-card
produce_type: vegetable   # or fruit; add the card twice to show both
max_recipes: 5            # recipes shown below the list (Mealie only)
```

```yaml
type: custom:seasonal-groceries-calendar-card
produce_type: fruit
max_rows: 15              # row limit, applied after sorting
```

```yaml
type: custom:seasonal-groceries-match-card
```

All cards accept `title`. Items are sorted: in season now first, then fewest pesticide residues, unknown last. The pesticide marker is green, orange or red, or *Unknown* when there is no data. Every card shows its sources in the footer.

### Match review

The card shows one ingredient at a time that still needs a look: a fuzzy match nobody confirmed, or an ingredient without a match.

| Button | Does |
|---|---|
| Correct | Confirms the suggested item |
| Wrong | Rejects the suggestion; the next suggestion is shown |
| Change… | Pick any seasonal item |
| No season | The ingredient is produce, but never in season (banana, avocado). It counts as *not* in season in a recipe's score |
| Ignore | Not produce (salt, oil); left out of the score |

Only administrators can change matches. A correction applies to every recipe that uses the ingredient. Ingredients that are not matched and not reviewed are left out of the score until you decide.

## Data sources

The calendar and the pesticide levels are transcribed from two public documents. **Please credit them wherever you share this:**

- **Seasonal calendar:** [Groente- en fruitkalender](https://www.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Consumenten/Veelgestelde%20vragen/Voedingscentrum%20seizoengroente-%20en%20fruitkalender.pdf) of the **Voedingscentrum**, compiled from information by **Velt** and supplemented with insights from **Bionext**.
- **Pesticide levels:** [Groente en fruit van het seizoen: lekkerder met minder pesticiden](https://www.pan-netherlands.org/eetwijzer/v-h-seizoen/) of **PAN Netherlands** (Pesticide Action Network), the average number of pesticide residues per item found in **NVWA** tests in 2021-2023. Items with fewer than 10 tests have no score and are shown as *Unknown*.

The colour bands are green up to 0.4 residues, orange up to 1.8 and red above for vegetables. For fruit they are 1.8 and 3, which are **provisional approximations**; the cards say so. All data lives in `custom_components/seasonal_groceries/data/produce.json`, including the credits, and can be corrected there.

This integration is not affiliated with, or endorsed by, any of these organisations.

## Adding a language

1. Add a member to the `Language` enum in `custom_components/seasonal_groceries/const.py`.
2. Add `names.<code>` (and optional `aliases.<code>`) to every item in `data/produce.json`; a test checks that none is missing.
3. Add `translations/<code>.json` (setup screens) and `frontend/src/translations/<code>.json` (cards).

## Removal

Remove the integration under **Settings → Devices & Services**; this also deletes the match corrections stored in Home Assistant. If you installed it with HACS, remove it there too. Mealie is not changed, except for aliases you let the integration add with *Save corrections as aliases in Mealie*; those stay in Mealie.

## Development

```bash
uv sync --group dev
uv run pytest                      # unit tests
uv run ruff check . && uv run ruff format --check .
cd custom_components/seasonal_groceries/frontend && npm ci && npm run build
```

A disposable Home Assistant and Mealie for manual testing:

```bash
docker compose -f dev/docker-compose.yml up -d
uv run python dev/seed_mealie.py       # Dutch recipes and foods in Mealie (http://localhost:9925)
uv run python dev/setup_ha.py          # onboards HA (http://localhost:8123, user dev), adds the integration and a test dashboard
uv run --group e2e playwright install chromium
uv run --group e2e pytest e2e          # browser checks of the cards
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Ideas for later are in [FUTURE_WORK.md](FUTURE_WORK.md).

## License

[MIT](LICENSE)
