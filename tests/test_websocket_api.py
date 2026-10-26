"""Tests for the WebSocket API and the correction actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.seasonal_groceries.const import DOMAIN
from custom_components.seasonal_groceries.coordinator import ResolveError
from custom_components.seasonal_groceries.mealie import (
    MealieConnectionError,
    MealieFood,
    MealieIngredient,
    MealieRecipe,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.plugins import FrozenDateTimeFactory
    from pytest_homeassistant_custom_component.typing import (
        MockHAClientWebSocket,
        WebSocketGenerator,
    )

MANUAL = {"mode": "manual", "url": "http://m", "token": "t", "verify_ssl": True}
TOMATO_FOOD = MealieFood(id="f-tom", name="tomaten", aliases=())


def _recipe(slug: str, *ingredients: MealieIngredient) -> MealieRecipe:
    return MealieRecipe(slug=slug, name=slug.title(), ingredients=ingredients)


def _text(text: str) -> MealieIngredient:
    return MealieIngredient(None, text)


RECIPES = [
    _recipe("soep", _text("pompoen"), _text("prei"), _text("olijfolie")),
    _recipe("salade", MealieIngredient("f-tom", "tomaten"), _text("pompoen")),
    _recipe("pasta", MealieIngredient("f-tom", "tomaten"), _text("aardbei")),
    _recipe("leeg", _text("zout")),
]


def _client() -> MagicMock:
    client = MagicMock()
    client.get_foods = AsyncMock(return_value=[TOMATO_FOOD])
    client.get_recipes = AsyncMock(return_value=RECIPES)
    client.add_food_alias = AsyncMock()
    return client


async def _setup(
    hass: HomeAssistant, options: dict[str, Any] | None = None, mealie: Any = None
) -> MockConfigEntry:
    await hass.config.async_set_time_zone("UTC")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"language": "nl", "mealie": mealie or MANUAL},
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def client(freezer: FrozenDateTimeFactory) -> AsyncIterator[MagicMock]:
    freezer.move_to("2026-10-15 12:00:00+00:00")
    fake = _client()
    with patch(
        "custom_components.seasonal_groceries.coordinator.client_for",
        return_value=fake,
    ):
        yield fake


@pytest.fixture
async def ws(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """One authenticated WebSocket connection per test."""
    return await hass_ws_client(hass)


async def _call(ws: MockHAClientWebSocket, **message: Any) -> dict[str, Any]:
    await ws.send_json_auto_id(message)
    return await ws.receive_json()


async def test_items_now_sorted_with_credits(
    hass: HomeAssistant, ws: MockHAClientWebSocket
) -> None:
    await _setup(hass, mealie={"mode": "none"})

    response = await _call(
        ws,
        type="seasonal_groceries/items",
        produce_type="vegetable",
        mode="now",
    )

    result = response["result"]
    assert result["month"] == 10
    rows = result["rows"]
    assert rows
    assert all(r["in_season"] for r in rows)
    assert rows[0]["band"] == "green"
    assert {"key", "name", "type", "months", "residues", "band", "in_season"} <= set(
        rows[0]
    )
    residues = [r["residues"] for r in rows if r["residues"] is not None]
    assert residues == sorted(residues)
    assert rows[-1]["band"] == "unknown"
    assert {"calendar", "pesticides"} <= set(result["credits"])
    assert "Voedingscentrum" in result["credits"]["calendar"]["organisations"]
    assert result["data_as_of"]


async def test_items_calendar_respects_max_rows_and_type(
    hass: HomeAssistant,
    ws: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-10-15 12:00:00+00:00")
    await _setup(hass, mealie={"mode": "none"})

    response = await _call(
        ws,
        type="seasonal_groceries/items",
        produce_type="fruit",
        mode="calendar",
        max_rows=5,
    )

    rows = response["result"]["rows"]
    assert len(rows) == 5
    assert {r["type"] for r in rows} == {"fruit"}
    assert all(len(r["months"]) >= 1 for r in rows)


async def test_items_use_the_grocery_language(
    hass: HomeAssistant, ws: MockHAClientWebSocket
) -> None:
    await _setup(hass, options={"language": "en"}, mealie={"mode": "none"})

    response = await _call(
        ws,
        type="seasonal_groceries/items",
        produce_type="vegetable",
        mode="calendar",
    )

    names = {r["name"] for r in response["result"]["rows"]}
    assert "tomato" in names
    assert "tomaat" not in names


async def test_recipes_ranked(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    response = await _call(ws, type="seasonal_groceries/recipes")

    result = response["result"]
    assert result["mealie_configured"] is True
    assert result["mealie_ok"] is True
    assert [(r["slug"], r["in_season"], r["total"]) for r in result["recipes"]] == [
        ("salade", 2, 2),
        ("soep", 2, 2),
        ("pasta", 1, 2),
    ]
    limited = await _call(ws, type="seasonal_groceries/recipes", limit=1)
    assert len(limited["result"]["recipes"]) == 1


async def test_recipes_without_mealie_configured(
    hass: HomeAssistant, ws: MockHAClientWebSocket
) -> None:
    await _setup(hass, mealie={"mode": "none"})

    response = await _call(ws, type="seasonal_groceries/recipes")

    assert response["result"] == {
        "recipes": [],
        "mealie_configured": False,
        "mealie_ok": True,
    }


async def test_recipes_when_mealie_down(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    client.get_recipes = AsyncMock(side_effect=MealieConnectionError("down"))
    await _setup(hass)

    response = await _call(ws, type="seasonal_groceries/recipes")

    assert response["result"]["recipes"] == []
    assert response["result"]["mealie_ok"] is False
    assert response["result"]["mealie_configured"] is True


async def test_review_queue_lists_entries(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    response = await _call(ws, type="seasonal_groceries/review_queue")

    entries = {e["text"]: e for e in response["result"]["entries"]}
    assert set(entries) == {"tomaten", "olijfolie", "zout"}
    assert entries["tomaten"]["current_item_key"] == "tomaat"
    assert entries["tomaten"]["ingredient_key"] == "food:f-tom"
    assert entries["tomaten"]["suggestions"][0] == "tomaat"


async def test_item_options_sorted_by_name(
    hass: HomeAssistant, ws: MockHAClientWebSocket
) -> None:
    await _setup(hass, mealie={"mode": "none"})

    response = await _call(ws, type="seasonal_groceries/item_options")

    options = response["result"]["options"]
    names = [o["name"] for o in options]
    assert names == sorted(names, key=str.casefold)
    assert {"key", "name", "type"} == set(options[0])


async def _resolve(ws: MockHAClientWebSocket, **fields: Any) -> dict[str, Any]:
    return await _call(ws, type="seasonal_groceries/review_resolve", **fields)


async def _queue_keys(ws: MockHAClientWebSocket) -> set[str]:
    response = await _call(ws, type="seasonal_groceries/review_queue")
    return {e["ingredient_key"] for e in response["result"]["entries"]}


async def test_resolve_confirm_removes_entry(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    response = await _resolve(ws, ingredient_key="food:f-tom", action="confirm")

    assert response["success"] is True
    assert "food:f-tom" not in await _queue_keys(ws)


async def test_resolve_wrong_advances_suggestion(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    await _resolve(ws, ingredient_key="food:f-tom", action="wrong")

    response = await _call(ws, type="seasonal_groceries/review_queue")
    entry = next(
        e for e in response["result"]["entries"] if e["ingredient_key"] == "food:f-tom"
    )
    assert entry["current_item_key"] != "tomaat"
    assert "tomaat" not in entry["suggestions"]


async def test_resolve_change_applies_to_all_recipes_sharing_ingredient(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    await _resolve(
        ws,
        ingredient_key="food:f-tom",
        action="change",
        item_key="aardbei",
    )

    response = await _call(ws, type="seasonal_groceries/recipes")
    ranked = {
        r["slug"]: (r["in_season"], r["total"]) for r in response["result"]["recipes"]
    }
    assert ranked["salade"] == (1, 2)
    assert ranked["pasta"] == (0, 2)
    assert "food:f-tom" not in await _queue_keys(ws)


async def test_resolve_no_season_changes_score(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    await _resolve(ws, ingredient_key="text:olijfolie", action="no_season")

    response = await _call(ws, type="seasonal_groceries/recipes")
    ranked = {
        r["slug"]: (r["in_season"], r["total"]) for r in response["result"]["recipes"]
    }
    assert ranked["soep"] == (2, 3)
    assert "text:olijfolie" not in await _queue_keys(ws)


async def test_resolve_ignore_removes_from_queue(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    await _resolve(ws, ingredient_key="text:zout", action="ignore")

    assert "text:zout" not in await _queue_keys(ws)


@pytest.mark.parametrize(("write_back", "expected_calls"), [(True, 1), (False, 0)])
async def test_alias_written_back_only_when_option_on(
    hass: HomeAssistant,
    ws: MockHAClientWebSocket,
    client: MagicMock,
    write_back: bool,  # noqa: FBT001
    expected_calls: int,
) -> None:
    await _setup(hass, options={"write_back_aliases": write_back})

    await _resolve(
        ws,
        ingredient_key="food:f-tom",
        action="change",
        item_key="tomaat",
    )

    assert client.add_food_alias.await_count == expected_calls
    if write_back:
        client.add_food_alias.assert_awaited_once_with("f-tom", "tomaat")


async def test_alias_not_written_for_free_text_or_ignore(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass, options={"write_back_aliases": True})

    await _resolve(
        ws,
        ingredient_key="text:olijfolie",
        action="change",
        item_key="prei",
    )
    await _resolve(ws, ingredient_key="food:f-tom", action="ignore")

    client.add_food_alias.assert_not_awaited()


async def test_subscribe_notifies_when_the_data_changes(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)
    await ws.send_json_auto_id({"type": "seasonal_groceries/subscribe"})
    assert (await ws.receive_json())["success"] is True

    await ws.send_json_auto_id(
        {
            "type": "seasonal_groceries/review_resolve",
            "ingredient_key": "text:zout",
            "action": "ignore",
        }
    )

    messages = [await ws.receive_json(), await ws.receive_json()]
    assert {m["type"] for m in messages} == {"event", "result"}


async def test_read_only_users_can_read_and_subscribe_but_not_resolve(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    client: MagicMock,
) -> None:
    await _setup(hass)
    reader = await hass_ws_client(hass, hass_read_only_access_token)

    for message in (
        {"type": "seasonal_groceries/recipes"},
        {"type": "seasonal_groceries/review_queue"},
        {"type": "seasonal_groceries/item_options"},
        {"type": "seasonal_groceries/subscribe"},
        {
            "type": "seasonal_groceries/items",
            "produce_type": "fruit",
            "mode": "now",
        },
    ):
        assert (await _call(reader, **message))["success"] is True, message

    denied = await _resolve(reader, ingredient_key="text:zout", action="ignore")
    assert denied["success"] is False
    assert denied["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "fields",
    [
        {"ingredient_key": "food:nope", "action": "ignore"},
        {"ingredient_key": "food:f-tom", "action": "change"},
        {"ingredient_key": "food:f-tom", "action": "change", "item_key": "ghost"},
        {"ingredient_key": "text:olijfolie", "action": "confirm"},
    ],
)
async def test_invalid_resolve_requests_error(
    hass: HomeAssistant,
    ws: MockHAClientWebSocket,
    client: MagicMock,
    fields: dict[str, str],
) -> None:
    await _setup(hass)

    response = await _resolve(ws, **fields)

    assert response["success"] is False


async def test_commands_error_when_integration_not_loaded(
    hass: HomeAssistant, ws: MockHAClientWebSocket
) -> None:
    entry = await _setup(hass, mealie={"mode": "none"})
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

    response = await _call(ws, type="seasonal_groceries/recipes")

    assert response["success"] is False


async def test_wrong_without_a_current_match_errors(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)

    response = await _resolve(ws, ingredient_key="text:olijfolie", action="wrong")

    assert response["success"] is False


async def test_wrong_on_an_explicit_choice_clears_it(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    await _setup(hass)
    await _resolve(ws, ingredient_key="food:f-tom", action="change", item_key="aardbei")

    await _resolve(ws, ingredient_key="food:f-tom", action="wrong")

    response = await _call(ws, type="seasonal_groceries/review_queue")
    entry = next(
        e for e in response["result"]["entries"] if e["ingredient_key"] == "food:f-tom"
    )
    assert entry["current_item_key"] != "aardbei"
    assert "aardbei" not in entry["suggestions"]


async def test_unknown_action_is_rejected_by_the_coordinator(
    hass: HomeAssistant, client: MagicMock
) -> None:
    entry = await _setup(hass)

    with pytest.raises(ResolveError):
        await entry.runtime_data.async_resolve_entry("text:zout", "explode")


async def test_failed_alias_write_back_still_applies_the_correction(
    hass: HomeAssistant, ws: MockHAClientWebSocket, client: MagicMock
) -> None:
    client.add_food_alias = AsyncMock(side_effect=MealieConnectionError("down"))
    await _setup(hass, options={"write_back_aliases": True})

    response = await _resolve(
        ws, ingredient_key="food:f-tom", action="change", item_key="tomaat"
    )

    assert response["success"] is True
    assert "food:f-tom" not in await _queue_keys(ws)
