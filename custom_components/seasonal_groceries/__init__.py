"""The Seasonal Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.frontend import (
    add_extra_js_url,
    remove_extra_js_url,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import config_validation as cv

from .const import CARD_MODULE_URL, DOMAIN, FRONTEND_PATH
from .coordinator import SeasonalGroceriesCoordinator
from .corrections import CorrectionsStore
from .websocket_api import async_register_commands

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

type SeasonalGroceriesConfigEntry = ConfigEntry[SeasonalGroceriesCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the WebSocket API; entries are set up separately."""
    async_register_commands(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SeasonalGroceriesConfigEntry
) -> bool:
    """
    Set up Seasonal Groceries from a config entry.

    A Mealie outage must not stop the seasonal information, so the first refresh
    may fail without failing the setup.
    """
    # Serve the built cards once per Home Assistant run, and load them on every
    # dashboard so they show up in the card picker.
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("static_path_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path=FRONTEND_PATH,
                    path=hass.config.path(f"custom_components/{DOMAIN}/www"),
                    cache_headers=False,
                )
            ]
        )
        domain_data["static_path_registered"] = True
    add_extra_js_url(hass, CARD_MODULE_URL)
    entry.async_on_unload(lambda: remove_extra_js_url(hass, CARD_MODULE_URL))

    corrections = CorrectionsStore(hass)
    await corrections.load()
    coordinator = SeasonalGroceriesCoordinator(hass, entry, corrections)
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    # A coordinator only polls while it has a listener; the cards add their own via
    # the subscribe command, this one keeps the data fresh when no dashboard is open.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))
    coordinator.async_start_month_listener()
    entry.async_on_unload(coordinator.async_stop_month_listener)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SeasonalGroceriesConfigEntry
) -> bool:
    """Unload a config entry."""
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: SeasonalGroceriesConfigEntry
) -> None:
    """Delete the stored corrections together with the entry."""
    await CorrectionsStore(hass).async_remove()
