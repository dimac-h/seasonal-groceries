"""Tests for the config flow and options flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)

import custom_components.seasonal_groceries as integration
from custom_components.seasonal_groceries.const import DOMAIN, Language

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

URL = "http://mealie.local:9000"


async def _start(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _to_mealie_menu(hass: HomeAssistant, language: str = "en") -> dict[str, Any]:
    result = await _start(hass)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"language": language}
    )


def _core_mealie_entry(hass: HomeAssistant) -> MockConfigEntry:
    mock_integration(hass, MockModule("mealie"))
    entry = MockConfigEntry(
        domain="mealie",
        title="Mealie",
        data={"host": "http://core:9000", "api_token": "core", "verify_ssl": True},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


def _field(result: dict[str, Any], name: str) -> tuple[Any, Any]:
    for marker, selector in result["data_schema"].schema.items():
        if marker == name:
            return marker, selector
    msg = f"no field {name}"
    raise AssertionError(msg)


async def test_user_flow_manual_mealie_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/users/self", json={"id": "u"})
    menu = await _to_mealie_menu(hass, "nl")
    assert menu["type"] is FlowResultType.MENU

    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"url": URL, "token": "abc", "verify_ssl": True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "language": "nl",
        "mealie": {"mode": "manual", "url": URL, "token": "abc", "verify_ssl": True},
    }


async def test_flow_offers_reuse_when_core_mealie_entry_exists(
    hass: HomeAssistant,
) -> None:
    _core_mealie_entry(hass)

    menu = await _to_mealie_menu(hass)

    assert menu["menu_options"] == ["reuse", "manual", "skip"]


async def test_flow_hides_reuse_when_none_found(hass: HomeAssistant) -> None:
    menu = await _to_mealie_menu(hass)

    assert menu["menu_options"] == ["manual", "skip"]


async def test_reuse_flow_stores_entry_id_not_credentials(
    hass: HomeAssistant,
) -> None:
    core = _core_mealie_entry(hass)
    menu = await _to_mealie_menu(hass)

    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "reuse"}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"entry_id": core.entry_id}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "language": "en",
        "mealie": {"mode": "integration", "entry_id": core.entry_id},
    }


async def test_flow_skip_mealie_creates_entry_without_credentials(
    hass: HomeAssistant,
) -> None:
    menu = await _to_mealie_menu(hass)

    result = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "skip"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"language": "en", "mealie": {"mode": "none"}}


async def test_invalid_auth_shows_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/users/self", status=401)
    menu = await _to_mealie_menu(hass)
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"url": URL, "token": "bad", "verify_ssl": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_shows_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/users/self", exc=ClientError)
    menu = await _to_mealie_menu(hass)
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"url": URL, "token": "t", "verify_ssl": True}
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_language_defaults_from_hass_language(hass: HomeAssistant) -> None:
    hass.config.language = "nl"
    marker, _ = _field(await _start(hass), "language")
    assert marker.default() == "nl"

    hass.config.language = "de"
    marker, _ = _field(await _start(hass), "language")
    assert marker.default() == "en"


async def test_language_choices_come_from_enum(hass: HomeAssistant) -> None:
    _, selector = _field(await _start(hass), "language")

    assert selector.config["options"] == [language.value for language in Language]


async def test_single_instance(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)

    result = await _start(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_toggles_write_back(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    form = await hass.config_entries.options.async_init(setup_integration.entry_id)
    assert form["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {"language": "en", "write_back_aliases": True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_integration.options == {"language": "en", "write_back_aliases": True}


async def test_options_language_change_reloads_entry(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    form = await hass.config_entries.options.async_init(setup_integration.entry_id)

    with patch.object(
        integration, "async_setup_entry", wraps=integration.async_setup_entry
    ) as setup:
        await hass.config_entries.options.async_configure(
            form["flow_id"], {"language": "nl", "write_back_aliases": False}
        )
        await hass.async_block_till_done()

    assert setup.call_count == 1
    assert setup_integration.options["language"] == "nl"


def _existing_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"language": "nl", "mealie": {"mode": "none"}},
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_changes_mealie_without_touching_the_rest(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/users/self", json={"id": "u"})
    entry = _existing_entry(hass)

    menu = await entry.start_reconfigure_flow(hass)
    assert menu["type"] is FlowResultType.MENU
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"url": URL, "token": "new", "verify_ssl": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        "language": "nl",
        "mealie": {"mode": "manual", "url": URL, "token": "new", "verify_ssl": True},
    }


async def test_reauth_replaces_the_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/users/self", json={"id": "u"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "mealie": {
                "mode": "manual",
                "url": URL,
                "token": "old",
                "verify_ssl": True,
            },
        },
    )
    entry.add_to_hass(hass)

    menu = await entry.start_reauth_flow(hass)
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"url": URL, "token": "fresh", "verify_ssl": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["mealie"]["token"] == "fresh"
