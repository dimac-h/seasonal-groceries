# Seasonal Groceries

**Seasonal Groceries** shows which vegetables and fruit are in season this month and how many pesticide residues are contaminating them. If you are using [Mealie](https://mealie.io) it shows which of your recipes are made of the most seasonal products. Eat what is in season, so your food does not come from glasshouses or travel halfway around the world! 😊

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dimac-h&repository=seasonal-groceries&category=integration)
[![Add Integration to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=seasonal_groceries)

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/dimac-h/seasonal-groceries/main/images/now-card.png" alt="The in-season-now card, showing fruit in season in October with pesticide levels and the most seasonal recipes" width="360"></td>
<td><img src="https://raw.githubusercontent.com/dimac-h/seasonal-groceries/main/images/calendar-card-dark.png" alt="The year calendar card in dark mode" width="360"></td>
</tr>
</table>

## Features

- **In season now:** a list of the vegetables or fruit in season this month.
- **Year calendar:** which month each item is in season.
- **Recipe ranking (optional):** your Mealie recipes sorted by the share of their fruit and vegetables that is in season.
- **Match review:** confirm or fix how a Mealie ingredient is matched to a seasonal item. Names and aliases you already have in Mealie are used first.


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

1. **Grocery language** (Dutch or English). The vegetables and fruit names are shown in this language, and your Mealie ingredients are matched against names in this language only. You can change it later in the integration options. The custom cards follow your HA language setting.
2. **Mealie (optional):** pick one of
   - *Use the existing Home Assistant Mealie integration* (offered when you have one). The URL and token are read from it every time, so a changed token is picked up automatically. Home Assistant's Mealie integration needs Mealie 3.2 or newer.
   - *Enter the Mealie URL and API token.* Create a token in Mealie under your profile settings.
   - *Skip:* you only get the seasonal information, no recipes.

There is the option to save corrections as aliases in Mealie so that when you correct a match, the seasonal item's name is also added as an alias to the linked Mealie food.

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
type: custom:seasonal-groceries-match-card # to confirm matches, otherwise ingredients are ignored
```

## Current data sources

The calendar and the pesticide levels are transcribed from two public documents.

- **Seasonal calendar:** [Groente- en fruitkalender](https://www.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Consumenten/Veelgestelde%20vragen/Voedingscentrum%20seizoengroente-%20en%20fruitkalender.pdf) of the **Voedingscentrum**, compiled from information by **Velt** and supplemented with insights from **Bionext**.
- **Pesticide levels:** [Groente en fruit van het seizoen: lekkerder met minder pesticiden](https://www.pan-netherlands.org/eetwijzer/v-h-seizoen/) of **PAN Netherlands** (Pesticide Action Network), the average number of pesticide residues per item found in **NVWA** tests in 2021-2023. Items with fewer than 10 tests have no score and are shown as *Unknown*.

This integration is not affiliated with, or endorsed by, any of these organizations.

## Removal

Remove the integration under **Settings → Devices & Services**; this also deletes the match corrections stored in Home Assistant. If you installed it with HACS, remove it there too. Mealie is not changed, except for aliases you let the integration add with *Save corrections as aliases in Mealie*; those stay in Mealie.

## License

[MIT](LICENSE)
