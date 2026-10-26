"""Fixtures for testing the Seasonal Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_component

from custom_components.seasonal_groceries.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integration loading in every test."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
def mock_frontend_component(hass: HomeAssistant) -> None:
    """Mock the frontend component that manifest.json depends on."""
    mock_component(hass, "frontend")


@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the seasonal_groceries integration."""
    await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(
        domain=DOMAIN, data={"language": "en", "mealie": {"mode": "none"}}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
