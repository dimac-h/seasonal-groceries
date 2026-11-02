"""Tests for the Mealie client and credential discovery."""

from __future__ import annotations

import json
import re
from dataclasses import replace
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
    MealieRecipe,
    credentials_for,
    credentials_from_entry,
    discover_mealie_entries,
    recipe_url,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

FIXTURES = Path(__file__).parent / "fixtures"
URL = "http://mealie.local:9000"
SOUP_ID = "9b016864-eff2-4a63-a155-28e6ca233187"
SALAD_ID = "568b0a37-db4e-4f0b-9310-5265db8bfc57"
OWNER_RATINGS = [
    {"recipeId": SOUP_ID, "rating": 3.7, "isFavorite": True},
    {"recipeId": SALAD_ID, "rating": 4.5, "isFavorite": False},
]


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _client(hass: HomeAssistant) -> MealieClient:
    return MealieClient(async_get_clientsession(hass), URL, "secret-token")


def _mock_user(
    aioclient_mock: AiohttpClientMocker,
    ratings: list[dict[str, Any]] | None = None,
    ratings_status: int = 200,
) -> None:
    """Mock the token owner and their ratings and favourites."""
    aioclient_mock.get(f"{URL}/api/users/self", json={"id": "u", "groupSlug": "home"})
    aioclient_mock.get(
        f"{URL}/api/users/self/ratings",
        status=ratings_status,
        json={
            "ratings": OWNER_RATINGS if ratings is None else ratings,
        },
    )


def _mock_recipes(
    aioclient_mock: AiohttpClientMocker,
    ratings: list[dict[str, Any]] | None = None,
    ratings_status: int = 200,
) -> None:
    _mock_user(aioclient_mock, ratings, ratings_status)
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


async def test_get_recipes_reads_display_fields(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)

    recipes = {r.slug: r for r in await _client(hass).get_recipes()}

    soup = recipes["pompoensoep"]
    assert soup.id == SOUP_ID
    assert soup.image == "b6ep"
    assert soup.description.startswith("Een romige soep")
    assert soup.tags == ("soep", "herfst")
    assert soup.group_slug == "home"
    bare = recipes["lege-schotel"]
    assert (bare.image, bare.description, bare.tags) == (None, "", ())


async def test_get_recipes_marks_favourites_and_owner_rating(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)

    recipes = {r.slug: r for r in await _client(hass).get_recipes()}

    # The list rating is an average over all users; only the owner's own counts.
    assert (recipes["pompoensoep"].favorite, recipes["pompoensoep"].rating) == (
        True,
        3.7,
    )
    assert (recipes["tomatensalade"].favorite, recipes["tomatensalade"].rating) == (
        False,
        4.5,
    )
    assert (recipes["bananenbrood"].favorite, recipes["bananenbrood"].rating) == (
        False,
        None,
    )


async def test_failing_ratings_request_leaves_the_recipes_without_ratings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock, ratings_status=404)

    recipes = await _client(hass).get_recipes()

    assert recipes
    assert all(r.rating is None and not r.favorite for r in recipes)


async def test_missing_group_slug_falls_back_to_home(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)
    aioclient_mock.get(f"{URL}/api/users/self", json={"id": "u"})

    recipes = await _client(hass).get_recipes()

    assert {r.group_slug for r in recipes} == {"home"}


async def test_get_image_returns_bytes_and_content_type(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        f"{URL}/api/media/recipes/abc/images/min-original.webp",
        content=b"img",
        headers={"Content-Type": "image/webp"},
    )
    recipe = MealieRecipe(slug="x", name="X", ingredients=(), id="abc", image="v")

    assert await _client(hass).get_image(recipe) == (b"img", "image/webp")
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer secret-token"


async def test_display_fields_refresh_even_when_the_recipe_is_cached(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)
    first = await _client(hass).get_recipes()
    aioclient_mock.clear_requests()
    _mock_recipes(
        aioclient_mock,
        ratings=[{"recipeId": SOUP_ID, "rating": 1.5, "isFavorite": False}],
    )

    second = {r.slug: r for r in await _client(hass).get_recipes(first)}

    assert (second["pompoensoep"].rating, second["pompoensoep"].favorite) == (
        1.5,
        False,
    )
    assert second["tomatensalade"].rating is None
    detail_calls = [
        c for c in aioclient_mock.mock_calls if "/api/recipes/" in str(c[1])
    ]
    assert detail_calls == []


@pytest.mark.parametrize(
    ("base", "expected_root"),
    [
        ("http://h/", "http://h"),
        ("http://h", "http://h"),
        ("https://h/mealie/", "https://h/mealie"),
    ],
)
def test_recipe_url_handles_slash_and_subpath(base: str, expected_root: str) -> None:
    recipe = MealieRecipe(slug="soep", name="Soep", ingredients=(), group_slug="home")

    assert recipe_url(base, recipe) == f"{expected_root}/g/home/r/soep"


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
    _mock_user(aioclient_mock)
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


async def test_missing_recipe_detail_is_skipped(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    listing = _fixture("mealie_recipes_list.json")
    _mock_user(aioclient_mock)
    aioclient_mock.get(f"{URL}/api/recipes", json=listing)
    gone = listing["items"][0]["slug"]
    for item in listing["items"]:
        if item["slug"] == gone:
            aioclient_mock.get(f"{URL}/api/recipes/{gone}", status=404)
        else:
            aioclient_mock.get(
                f"{URL}/api/recipes/{item['slug']}",
                json=_fixture(f"mealie_recipe_{item['slug']}.json"),
            )

    recipes = await _client(hass).get_recipes()

    assert gone not in {r.slug for r in recipes}
    assert len(recipes) == len(listing["items"]) - 1


async def test_detail_server_error_still_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    listing = _fixture("mealie_recipes_list.json")
    _mock_user(aioclient_mock)
    aioclient_mock.get(f"{URL}/api/recipes", json=listing)
    aioclient_mock.get(re.compile(rf"{URL}/api/recipes/.+"), status=500)

    with pytest.raises(MealieConnectionError):
        await _client(hass).get_recipes()


async def test_unchanged_recipes_are_not_fetched_again(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)
    first = await _client(hass).get_recipes()
    aioclient_mock.clear_requests()
    _mock_recipes(aioclient_mock)

    second = await _client(hass).get_recipes(first)

    assert second == first
    detail_calls = [
        c for c in aioclient_mock.mock_calls if "/api/recipes/" in str(c[1])
    ]
    assert detail_calls == []


async def test_changed_recipe_is_fetched_again(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_recipes(aioclient_mock)
    first = await _client(hass).get_recipes()
    stale = [replace(r, updated="older") for r in first]
    aioclient_mock.clear_requests()
    _mock_recipes(aioclient_mock)

    await _client(hass).get_recipes(stale)

    detail_calls = [
        c for c in aioclient_mock.mock_calls if "/api/recipes/" in str(c[1])
    ]
    assert len(detail_calls) == len(first)


async def test_malformed_response_is_a_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/foods", json={"unexpected": True})

    with pytest.raises(MealieConnectionError):
        await _client(hass).get_foods()


async def test_non_json_response_is_a_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{URL}/api/foods", text="<html>proxy error</html>")

    with pytest.raises(MealieConnectionError):
        await _client(hass).get_foods()
