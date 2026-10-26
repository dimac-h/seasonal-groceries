"""The Seasonal Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import SeasonalGroceriesCoordinator
from .corrections import CorrectionsStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

type SeasonalGroceriesConfigEntry = ConfigEntry[SeasonalGroceriesCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration (config entries only)."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SeasonalGroceriesConfigEntry
) -> bool:
    """
    Set up Seasonal Groceries from a config entry.

    A Mealie outage must not stop the seasonal information, so the first refresh
    may fail without failing the setup.
    """
    corrections = CorrectionsStore(hass)
    await corrections.load()
    coordinator = SeasonalGroceriesCoordinator(hass, entry, corrections)
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    coordinator.async_start_month_listener()
    entry.async_on_unload(coordinator.async_stop_month_listener)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SeasonalGroceriesConfigEntry
) -> bool:
    """Unload a config entry."""
    return True
