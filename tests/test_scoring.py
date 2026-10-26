"""Tests for resolving ingredients and scoring recipes."""

from __future__ import annotations

import pytest

from custom_components.seasonal_groceries.const import Language
from custom_components.seasonal_groceries.corrections import Correction
from custom_components.seasonal_groceries.dataset import load_dataset
from custom_components.seasonal_groceries.mealie import MealieIngredient, MealieRecipe
from custom_components.seasonal_groceries.scoring import (
    RecipeScore,
    Resolved,
    rank,
    resolve,
    score_recipe,
)

NL = load_dataset(Language.NL)
OCTOBER = 10


def _ing(text: str, food_id: str | None = None) -> MealieIngredient:
    return MealieIngredient(food_id=food_id, text=text)


def _recipe(*texts: str, name: str = "r") -> MealieRecipe:
    return MealieRecipe(slug=name, name=name, ingredients=tuple(_ing(t) for t in texts))


def _score(*texts: str, month: int = OCTOBER) -> RecipeScore | None:
    recipe = _recipe(*texts)
    resolutions = [resolve(i, {}, NL, {}) for i in recipe.ingredients]
    return score_recipe(recipe, resolutions, NL, month)


def test_resolve_exact_is_confirmed() -> None:
    assert resolve(_ing("pompoen"), {}, NL, {}) == Resolved(
        "item", "pompoen", confirmed=True
    )


def test_resolve_fuzzy_is_unconfirmed() -> None:
    assert resolve(_ing("tomaten"), {}, NL, {}) == Resolved(
        "item", "tomaat", confirmed=False
    )


def test_resolve_no_match_is_unreviewed() -> None:
    assert resolve(_ing("olijfolie"), {}, NL, {}) == Resolved(
        "unreviewed", None, confirmed=False
    )


def test_correction_overrides_match() -> None:
    corrections = {
        "text:peer": Correction(status="item", item_key="appel", confirmed=True)
    }

    assert resolve(_ing("peer"), {}, NL, corrections) == Resolved(
        "item", "appel", confirmed=True
    )


@pytest.mark.parametrize(
    ("status", "kind"), [("ignored", "ignored"), ("no_season", "no_season")]
)
def test_correction_statuses(status: str, kind: str) -> None:
    corrections = {"text:peer": Correction(status=status)}  # type: ignore[arg-type]

    assert resolve(_ing("peer"), {}, NL, corrections) == Resolved(
        kind, None, confirmed=True
    )  # type: ignore[arg-type]


def test_rejection_without_choice_asks_the_matcher_without_that_item() -> None:
    corrections = {"text:tomaten": Correction(status="item", rejected=["tomaat"])}

    result = resolve(_ing("tomaten"), {}, NL, corrections)

    assert result.item_key != "tomaat"
    assert result.confirmed is False


def test_all_in_season_is_full_ratio() -> None:
    score = _score("pompoen", "prei", "boerenkool")

    assert (score.in_season, score.total) == (3, 3)  # type: ignore[union-attr]


def test_no_season_counts_as_not_in_season() -> None:
    recipe = _recipe("pompoen", "banaan")
    resolutions = [
        Resolved("item", "pompoen", confirmed=True),
        Resolved("no_season", None, confirmed=True),
    ]

    score = score_recipe(recipe, resolutions, NL, OCTOBER)

    assert (score.in_season, score.total) == (1, 2)  # type: ignore[union-attr]


def test_ignored_and_unreviewed_are_not_counted() -> None:
    recipe = _recipe("pompoen", "zout", "olijfolie")
    resolutions = [
        Resolved("item", "pompoen", confirmed=True),
        Resolved("ignored", None, confirmed=True),
        Resolved("unreviewed", None, confirmed=False),
    ]

    score = score_recipe(recipe, resolutions, NL, OCTOBER)

    assert (score.in_season, score.total) == (1, 1)  # type: ignore[union-attr]


def test_zero_produce_returns_none() -> None:
    assert _score("zout", "olijfolie") is None


def test_out_of_season_item_counts_in_total_only() -> None:
    score = _score("aardbei", "pompoen")

    assert (score.in_season, score.total) == (1, 2)  # type: ignore[union-attr]


def test_rank_ratio_then_total_then_name() -> None:
    scores = [
        RecipeScore("a", "Bravo", 5, 5),
        RecipeScore("b", "Alpha", 6, 6),
        RecipeScore("c", "Charlie", 3, 6),
        RecipeScore("d", "Alpha too", 5, 5),
        RecipeScore("e", "Delta", 9, 10),
    ]

    assert [s.slug for s in rank(scores)] == ["b", "d", "a", "e", "c"]
