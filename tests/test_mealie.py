"""Tests for the Mealie client and credential discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)

from custom_components.seasonal_groceries.mealie import (
    MealieAuthError,
    MealieClient,
    MealieConnectionError,
    MealieCredentials,
    credentials_for,
    credentials_from_entry,
    discover_mealie_entries,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

FIXTURES = Path(__file__).parent / "fixtures"
URL = "http://mealie.local:9000"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _client(hass: HomeAssistant) -> MealieClient:
    return MealieClient(async_get_clientsession(hass), URL, "secret-token")


def _mock_recipes(aioclient_mock: AiohttpClientMocker) -> None:
    listing = _fixture("mealie_recipes_list.json")
    aioclient_mock.get(f"{URL}/api/recipes", json=listing)
    for item in listing["items"]:
        aioclient_mock.get(
            f"{URL}/api/recipes/{item['slug']}",
            json=_fixture(f"mealie_recipe_{item['slug']}.json"),
        )


async def test_get_recipes_parses_linked_and_free_text_ingredients(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)

    recipes = {r.slug: r for r in await _client(hass).get_recipes()}

    assert set(recipes) == {
        "pompoensoep",
        "tomatensalade",
        "bananenbrood",
        "lege-schotel",
    }
    soup = recipes["pompoensoep"]
    assert soup.name == "Pompoensoep"
    assert [i.text for i in soup.ingredients] == ["pompoen", "prei", "olijfolie"]
    assert all(i.food_id for i in soup.ingredients)
    salad = recipes["tomatensalade"]
    assert [i.text for i in salad.ingredients] == [
        "tomaat",
        "verse basilicum",
        "olijfolie",
    ]
    assert [i.food_id is None for i in salad.ingredients] == [False, True, False]
    assert recipes["lege-schotel"].ingredients[0].text == "zout"


async def test_get_recipes_sends_bearer_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)

    await _client(hass).get_recipes()

    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer secret-token"


async def test_get_recipes_follows_pagination(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    listing = _fixture("mealie_recipes_list.json")
    first, second = listing["items"][:2], listing["items"][2:]
    page2 = {**listing, "page": 2, "total_pages": 2, "items": second}
    page1 = {**listing, "page": 1, "total_pages": 2, "items": first}
    aioclient_mock.get(f"{URL}/api/recipes?page=2", json=page2)
    aioclient_mock.get(f"{URL}/api/recipes", json=page1)
    for item in listing["items"]:
        aioclient_mock.get(
            f"{URL}/api/recipes/{item['slug']}",
            json=_fixture(f"mealie_recipe_{item['slug']}.json"),
        )

    recipes = await _client(hass).get_recipes()

    assert len(recipes) == len(listing["items"])


async def test_get_foods_includes_aliases(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/foods", json=_fixture("mealie_foods.json"))

    foods = {f.name: f for f in await _client(hass).get_foods()}

    assert foods["tomaat"].aliases == ("tomaten", "pomodori")
    assert foods["pompoen"].aliases == ()


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_error_maps_to_mealie_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    aioclient_mock.get(f"{URL}/api/foods", status=status)

    with pytest.raises(MealieAuthError):
        await _client(hass).get_foods()


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/foods", exc=ClientError)

    with pytest.raises(MealieConnectionError):
        await _client(hass).get_foods()


async def test_server_error_is_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/foods", status=500)

    with pytest.raises(MealieConnectionError):
        await _client(hass).get_foods()


async def test_validate_calls_current_user(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/users/self", json={"id": "x"})

    await _client(hass).validate()

    assert aioclient_mock.call_count == 1


async def test_add_food_alias_sends_request(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    tomaat = next(
        f for f in _fixture("mealie_foods.json")["items"] if f["name"] == "tomaat"
    )
    aioclient_mock.get(f"{URL}/api/foods/{tomaat['id']}", json=tomaat)
    aioclient_mock.put(f"{URL}/api/foods/{tomaat['id']}", json=tomaat)

    await _client(hass).add_food_alias(tomaat["id"], "tomatoes")

    put = next(c for c in aioclient_mock.mock_calls if c[0] == "PUT")
    assert [a["name"] for a in put[2]["aliases"]] == ["tomaten", "pomodori", "tomatoes"]


async def test_add_food_alias_skips_existing_alias(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    tomaat = next(
        f for f in _fixture("mealie_foods.json")["items"] if f["name"] == "tomaat"
    )
    aioclient_mock.get(f"{URL}/api/foods/{tomaat['id']}", json=tomaat)
    aioclient_mock.put(f"{URL}/api/foods/{tomaat['id']}", json=tomaat)

    await _client(hass).add_food_alias(tomaat["id"], "Tomaten")

    assert [c for c in aioclient_mock.mock_calls if c[0] == "PUT"] == []


def _core_entry(hass: HomeAssistant, **data: Any) -> MockConfigEntry:
    # Stub HA's own Mealie integration: the real one needs the aiomealie library.
    mock_integration(hass, MockModule("mealie"))
    entry = MockConfigEntry(
        domain="mealie",
        title="Mealie",
        data={
            "host": "http://core-mealie:9000",
            "api_token": "core-token",
            "verify_ssl": False,
        }
        | data,
    )
    entry.add_to_hass(hass)
    return entry


async def test_discover_returns_only_loaded_core_entries(hass: HomeAssistant) -> None:
    loaded = _core_entry(hass)
    loaded.mock_state(hass, ConfigEntryState.LOADED)
    _core_entry(hass)  # not loaded
    MockConfigEntry(domain="other").add_to_hass(hass)

    assert discover_mealie_entries(hass) == [loaded]


async def test_credentials_from_core_entry(hass: HomeAssistant) -> None:
    entry = _core_entry(hass)

    assert credentials_from_entry(entry) == MealieCredentials(
        url="http://core-mealie:9000", token="core-token", verify_ssl=False
    )


async def test_credentials_for_modes(hass: HomeAssistant) -> None:
    entry = _core_entry(hass)

    assert credentials_for(hass, {"mode": "none"}) is None
    assert credentials_for(
        hass, {"mode": "manual", "url": URL, "token": "t", "verify_ssl": True}
    ) == MealieCredentials(url=URL, token="t", verify_ssl=True)
    assert credentials_for(
        hass, {"mode": "integration", "entry_id": entry.entry_id}
    ) == MealieCredentials(
        url="http://core-mealie:9000", token="core-token", verify_ssl=False
    )


async def test_reused_credentials_follow_the_core_entry(hass: HomeAssistant) -> None:
    entry = _core_entry(hass)
    mealie = {"mode": "integration", "entry_id": entry.entry_id}

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "api_token": "rotated"}
    )

    creds = credentials_for(hass, mealie)
    assert creds is not None
    assert creds.token == "rotated"


async def test_removed_core_entry_is_unavailable(hass: HomeAssistant) -> None:
    entry = _core_entry(hass)
    mealie = {"mode": "integration", "entry_id": entry.entry_id}
    await hass.config_entries.async_remove(entry.entry_id)

    with pytest.raises(MealieConnectionError):
        credentials_for(hass, mealie)
