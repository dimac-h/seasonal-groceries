"""Fixtures for testing the Seasonal Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_component

from custom_components.seasonal_groceries.const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

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


@pytest.fixture(autouse=True)
async def http_component(hass: HomeAssistant) -> AsyncIterator[None]:
    """
    Set up http without really serving files.

    The test WebSocket client starts the server, and a started server refuses new
    static paths, so registering them is stubbed (test_init covers the call).
    """
    await async_setup_component(hass, "http", {})
    with patch.object(hass.http, "async_register_static_paths", AsyncMock()):
        yield


@pytest.fixture(autouse=True)
def add_extra_js_url_mock() -> Iterator[MagicMock]:
    """Stub the frontend's extra-module registry."""
    with patch("custom_components.seasonal_groceries.add_extra_js_url") as mock:
        yield mock


@pytest.fixture(autouse=True)
def remove_extra_js_url_mock() -> Iterator[MagicMock]:
    """Stub the frontend's extra-module registry cleanup used on unload."""
    with patch("custom_components.seasonal_groceries.remove_extra_js_url") as mock:
        yield mock


@pytest.fixture(autouse=True)
async def unload_entries(hass: HomeAssistant) -> AsyncIterator[None]:
    """Unload loaded entries so coordinator refresh timers do not linger."""
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


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
