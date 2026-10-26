"""Tests for ingredient matching against the seasonal dataset."""

from __future__ import annotations

import pytest

from custom_components.seasonal_groceries.const import Language
from custom_components.seasonal_groceries.dataset import load_dataset
from custom_components.seasonal_groceries.matching import match_ingredient, normalise
from custom_components.seasonal_groceries.mealie import MealieFood, MealieIngredient

NL = load_dataset(Language.NL)
EN = load_dataset(Language.EN)


def _text(text: str) -> MealieIngredient:
    return MealieIngredient(food_id=None, text=text)


def test_normalise_folds_case_accents_and_punctuation() -> None:
    assert normalise("  Tomaten (vers)! ") == "tomaten vers"
    assert normalise("Crème   fraîche") == "creme fraiche"
    assert normalise("") == ""


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("tomaat", "tomaat"),
        ("Pompoen", "pompoen"),
        ("uien", "ui"),
        ("wortels", "wortel"),
        ("courgettes", "courgette"),
        ("rode kool", "rodekool"),
    ],
)
def test_exact_matches_in_dutch(text: str, key: str) -> None:
    match = match_ingredient(_text(text), {}, NL)
    assert (match.kind, match.item_key) == ("exact", key)


def test_exact_matches_in_english() -> None:
    assert match_ingredient(_text("tomatoes"), {}, EN).item_key == "tomaat"
    assert match_ingredient(_text("Zucchini"), {}, EN).item_key == "courgette"


def test_matches_only_the_datasets_language() -> None:
    assert match_ingredient(_text("tomaat"), {}, NL).kind == "exact"
    assert match_ingredient(_text("tomaat"), {}, EN).kind != "exact"
    assert match_ingredient(_text("tomato"), {}, EN).kind == "exact"
    assert match_ingredient(_text("tomato"), {}, NL).kind != "exact"


def test_mealie_alias_gives_exact() -> None:
    foods = {"f1": MealieFood(id="f1", name="roma", aliases=("tomaat",))}
    ingredient = MealieIngredient(food_id="f1", text="roma")

    match = match_ingredient(ingredient, foods, NL)

    assert (match.kind, match.item_key) == ("exact", "tomaat")


def test_fuzzy_match_has_suggestions_best_first() -> None:
    match = match_ingredient(_text("tomaten"), {}, NL)

    assert (match.kind, match.item_key) == ("fuzzy", "tomaat")
    assert match.suggestions[0] == "tomaat"
    assert len(match.suggestions) <= 3


def test_fuzzy_match_on_a_word_inside_longer_text() -> None:
    match = match_ingredient(_text("verse tomaten"), {}, NL)

    assert match.item_key == "tomaat"


def test_typo_is_fuzzy() -> None:
    assert match_ingredient(_text("pompoem"), {}, NL).item_key == "pompoen"


def test_no_match_returns_none() -> None:
    match = match_ingredient(_text("olijfolie"), {}, NL)

    assert (match.kind, match.item_key) == ("none", None)
    assert len(match.suggestions) <= 3


def test_rejected_item_is_never_returned_or_suggested() -> None:
    match = match_ingredient(_text("tomaten"), {}, NL, rejected=frozenset({"tomaat"}))

    assert match.item_key != "tomaat"
    assert "tomaat" not in match.suggestions


def test_empty_text_is_none() -> None:
    match = match_ingredient(_text("   "), {}, NL)

    assert (match.kind, match.item_key, match.suggestions) == ("none", None, ())
