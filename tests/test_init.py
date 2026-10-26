"""Tests for setup and unload of the integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.seasonal_groceries.const import DOMAIN
from custom_components.seasonal_groceries.coordinator import (
    SeasonalGroceriesCoordinator,
)
from custom_components.seasonal_groceries.corrections import Correction
from custom_components.seasonal_groceries.mealie import MealieConnectionError


async def test_entry_loads_and_unloads(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    assert setup_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_creates_coordinator(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    coordinator = setup_integration.runtime_data

    assert isinstance(coordinator, SeasonalGroceriesCoordinator)
    assert coordinator.data.mealie_configured is False


async def test_entry_loads_even_when_mealie_is_down(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "nl",
            "mealie": {"mode": "manual", "url": "http://m", "token": "t"},
        },
    )
    entry.add_to_hass(hass)
    client = MagicMock()
    client.get_foods = AsyncMock(side_effect=MealieConnectionError("down"))

    with patch(
        "custom_components.seasonal_groceries.coordinator.client_for",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.last_update_success is False
    assert entry.runtime_data.dataset.items


async def test_frontend_module_registered_once_across_reload(
    hass: HomeAssistant,
    add_extra_js_url_mock: MagicMock,
    remove_extra_js_url_mock: MagicMock,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={"language": "en", "mealie": {"mode": "none"}}
    )
    entry.add_to_hass(hass)
    register = AsyncMock()

    with patch.object(hass.http, "async_register_static_paths", register):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    url = "/seasonal_groceries_frontend/seasonal-groceries-cards.js"
    assert [c.args for c in add_extra_js_url_mock.call_args_list] == [(hass, url)] * 2
    remove_extra_js_url_mock.assert_called_once_with(hass, url)
    assert register.await_count == 1
    config = register.await_args.args[0][0]
    assert config.url_path == "/seasonal_groceries_frontend"
    assert config.path.endswith("custom_components/seasonal_groceries/www")


async def test_removing_the_entry_deletes_stored_corrections(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={"language": "en", "mealie": {"mode": "none"}}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await entry.runtime_data.corrections.set("text:zout", Correction(status="ignored"))
    assert "seasonal_groceries.corrections" in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert "seasonal_groceries.corrections" not in hass_storage
