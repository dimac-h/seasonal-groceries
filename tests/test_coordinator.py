"""Tests for the coordinator that builds recipe rankings and the review queue."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

import custom_components.seasonal_groceries.coordinator as coordinator_module
from custom_components.seasonal_groceries.const import DOMAIN
from custom_components.seasonal_groceries.coordinator import (
    SeasonalGroceriesCoordinator,
)
from custom_components.seasonal_groceries.corrections import (
    Correction,
    CorrectionsStore,
)
from custom_components.seasonal_groceries.mealie import (
    MealieAuthError,
    MealieConnectionError,
    MealieIngredient,
    MealieRecipe,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.plugins import FrozenDateTimeFactory

_PATCHERS: list[Any] = []
MANUAL = {"mode": "manual", "url": "http://m", "token": "t", "verify_ssl": True}


def _recipe(slug: str, *texts: str) -> MealieRecipe:
    return MealieRecipe(
        slug=slug,
        name=slug.title(),
        ingredients=tuple(MealieIngredient(None, t) for t in texts),
    )


RECIPES = [
    _recipe("soep", "pompoen", "prei", "olijfolie"),
    _recipe("salade", "tomaten", "pompoen"),
    _recipe("kiwi", "kiwibes"),
    _recipe("leeg", "zout"),
]


def _fake_client(recipes: list[MealieRecipe] = RECIPES) -> MagicMock:
    client = MagicMock()
    client.get_foods = AsyncMock(return_value=[])
    client.get_recipes = AsyncMock(return_value=recipes)
    return client


async def _coordinator(
    hass: HomeAssistant, mealie: dict | None = None, client: MagicMock | None = None
) -> tuple[SeasonalGroceriesCoordinator, CorrectionsStore]:
    await hass.config.async_set_time_zone("UTC")
    entry = MockConfigEntry(
        domain=DOMAIN, data={"language": "nl", "mealie": mealie or MANUAL}
    )
    entry.add_to_hass(hass)
    corrections = CorrectionsStore(hass)
    await corrections.load()
    coordinator = SeasonalGroceriesCoordinator(hass, entry, corrections)
    patcher = patch(
        "custom_components.seasonal_groceries.coordinator.client_for",
        return_value=client or _fake_client(),
    )
    patcher.start()
    _PATCHERS.append(patcher)
    return coordinator, corrections


@pytest.fixture(autouse=True)
def _stop_patchers() -> Iterator[None]:
    yield
    # Only stop our own patches: patch.stopall() would also undo the ones the
    # Home Assistant test plugin relies on.
    while _PATCHERS:
        _PATCHERS.pop().stop()


async def test_refresh_builds_ranked_recipes_and_queue(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-15 12:00:00+00:00")
    coordinator, _ = await _coordinator(hass)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.mealie_configured is True
    ranked = [(r.slug, r.in_season, r.total) for r in coordinator.data.recipes]
    # olijfolie is unreviewed (not counted), tomaten is a fuzzy match (counted);
    # equal ratios rank by number of produce ingredients, then by name.
    assert ranked == [("salade", 2, 2), ("soep", 2, 2), ("kiwi", 1, 1)]


async def test_queue_contains_unconfirmed_fuzzy_and_unreviewed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-15 12:00:00+00:00")
    coordinator, _ = await _coordinator(hass)

    await coordinator.async_refresh()

    queue = {e.text: e for e in coordinator.data.queue}
    assert set(queue) == {"tomaten", "olijfolie", "zout"}
    assert queue["tomaten"].current_item_key == "tomaat"
    assert queue["tomaten"].suggestions[0] == "tomaat"
    assert queue["olijfolie"].current_item_key is None
    assert queue["tomaten"].ingredient_key == "text:tomaten"


async def test_mealie_down_sets_update_failed(hass: HomeAssistant) -> None:
    client = _fake_client()
    client.get_recipes = AsyncMock(side_effect=MealieConnectionError("down"))
    coordinator, _ = await _coordinator(hass, client=client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.dataset.items


async def test_removed_core_entry_fails_the_update(hass: HomeAssistant) -> None:
    coordinator, _ = await _coordinator(
        hass, mealie={"mode": "integration", "entry_id": "gone"}
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_no_mealie_skips_fetch_and_has_empty_data(hass: HomeAssistant) -> None:
    client = _fake_client()
    coordinator, _ = await _coordinator(hass, mealie={"mode": "none"}, client=client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.mealie_configured is False
    assert coordinator.data.recipes == []
    assert coordinator.data.queue == []
    client.get_recipes.assert_not_called()


async def test_recompute_applies_corrections_to_every_recipe(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-15 12:00:00+00:00")
    coordinator, corrections = await _coordinator(hass)
    await coordinator.async_refresh()

    await corrections.set("text:pompoen", Correction(status="no_season"))
    coordinator.async_recompute()

    ranked = {r.slug: (r.in_season, r.total) for r in coordinator.data.recipes}
    assert ranked["soep"] == (1, 2)
    assert ranked["salade"] == (1, 2)


async def test_month_rollover_recomputes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-31 23:59:00+00:00")
    coordinator, _ = await _coordinator(hass)
    await coordinator.async_refresh()
    coordinator.async_start_month_listener()
    assert {r.slug: r.in_season for r in coordinator.data.recipes}["kiwi"] == 1

    freezer.move_to("2026-11-01 00:00:10+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert {r.slug: r.in_season for r in coordinator.data.recipes}["kiwi"] == 0
    coordinator.async_stop_month_listener()


async def test_dataset_file_is_read_off_the_event_loop(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-15 12:00:00+00:00")
    loop_thread = threading.current_thread()
    threads: list[threading.Thread] = []
    real = coordinator_module.load_dataset

    def recording(*args: Any, **kwargs: Any) -> Any:
        threads.append(threading.current_thread())
        return real(*args, **kwargs)

    coordinator, _ = await _coordinator(hass)
    with patch.object(coordinator_module, "load_dataset", recording):
        await coordinator.async_refresh()

    assert threads
    assert all(thread is not loop_thread for thread in threads)


async def test_month_rollover_notifies_listeners_on_the_event_loop(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-31 23:59:00+00:00")
    loop_thread = threading.current_thread()
    notified: list[threading.Thread] = []
    coordinator, _ = await _coordinator(hass)
    await coordinator.async_refresh()
    coordinator.async_add_listener(lambda: notified.append(threading.current_thread()))
    coordinator.async_start_month_listener()

    freezer.move_to("2026-11-01 00:00:10+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    coordinator.async_stop_month_listener()

    assert notified
    assert all(thread is loop_thread for thread in notified)


async def test_recompute_keeps_the_mealie_failure_state(hass: HomeAssistant) -> None:
    client = _fake_client()
    client.get_recipes = AsyncMock(side_effect=MealieConnectionError("down"))
    coordinator, corrections = await _coordinator(hass, client=client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    await corrections.set("text:zout", Correction(status="ignored"))
    coordinator.async_recompute()

    assert coordinator.last_update_success is False
    assert coordinator.data.mealie_configured is True


async def test_auth_failure_starts_reauth(hass: HomeAssistant) -> None:
    client = _fake_client()
    client.get_foods = AsyncMock(side_effect=MealieAuthError("revoked"))
    coordinator, _ = await _coordinator(hass, client=client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert list(coordinator.config_entry.async_get_active_flows(hass, {"reauth"}))
