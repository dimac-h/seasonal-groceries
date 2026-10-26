"""Tests for the persisted ingredient corrections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.seasonal_groceries.corrections import (
    Correction,
    CorrectionsStore,
    ingredient_key,
)
from custom_components.seasonal_groceries.mealie import MealieIngredient

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def test_key_prefers_food_id() -> None:
    ingredient = MealieIngredient(food_id="abc", text="Tomaten")

    assert ingredient_key(ingredient) == "food:abc"


def test_key_falls_back_to_normalised_text() -> None:
    a = MealieIngredient(food_id=None, text="Verse  Tomaten!")
    b = MealieIngredient(food_id=None, text="verse tomaten")

    assert ingredient_key(a) == ingredient_key(b) == "text:verse tomaten"


async def test_empty_store_has_no_corrections(hass: HomeAssistant) -> None:
    store = CorrectionsStore(hass)
    await store.load()

    assert store.all() == {}
    assert store.get("food:x") is None


async def test_roundtrip_persists(hass: HomeAssistant, hass_storage: dict) -> None:
    first = CorrectionsStore(hass)
    await first.load()
    await first.set(
        "food:abc",
        Correction(status="item", item_key="tomaat", confirmed=True, rejected=["peer"]),
    )
    await first.set("text:zout", Correction(status="ignored"))

    second = CorrectionsStore(hass)
    await second.load()

    assert second.get("food:abc") == Correction(
        status="item", item_key="tomaat", confirmed=True, rejected=["peer"]
    )
    assert second.get("text:zout") == Correction(status="ignored")


async def test_rejected_accumulates_without_duplicates(hass: HomeAssistant) -> None:
    store = CorrectionsStore(hass)
    await store.load()

    await store.add_rejection("food:abc", "tomaat")
    await store.add_rejection("food:abc", "peer")
    await store.add_rejection("food:abc", "tomaat")

    correction = store.get("food:abc")
    assert correction == Correction(
        status="item", item_key=None, confirmed=False, rejected=["tomaat", "peer"]
    )


async def test_add_rejection_keeps_an_existing_choice(hass: HomeAssistant) -> None:
    store = CorrectionsStore(hass)
    await store.load()
    await store.set(
        "food:abc", Correction(status="item", item_key="appel", confirmed=True)
    )

    await store.add_rejection("food:abc", "peer")

    assert store.get("food:abc") == Correction(
        status="item", item_key="appel", confirmed=True, rejected=["peer"]
    )


def test_key_ignores_the_quantity() -> None:
    a = MealieIngredient(food_id=None, text="400 g tomaten")
    b = MealieIngredient(food_id=None, text="500 g Tomaten")

    assert ingredient_key(a) == ingredient_key(b) == "text:tomaten"


def test_keys_of_non_latin_text_do_not_collide() -> None:
    tofu = ingredient_key(MealieIngredient(food_id=None, text="豆腐"))
    miso = ingredient_key(MealieIngredient(food_id=None, text="味噌"))

    assert tofu != miso
    assert tofu != "text:"
