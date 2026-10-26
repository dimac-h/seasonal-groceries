"""Resolve recipe ingredients and score how seasonal a recipe is."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .corrections import ingredient_key
from .matching import match_ingredient

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from .corrections import Correction
    from .dataset import Dataset
    from .mealie import MealieFood, MealieIngredient, MealieRecipe

ResolvedKind = Literal["item", "no_season", "ignored", "unreviewed"]


@dataclass(frozen=True)
class Resolved:
    """What an ingredient turned out to be."""

    kind: ResolvedKind
    item_key: str | None
    confirmed: bool = field(kw_only=True)


@dataclass(frozen=True)
class RecipeScore:
    """How many of a recipe's produce ingredients are in season."""

    slug: str
    name: str
    in_season: int
    total: int


def resolve(
    ingredient: MealieIngredient,
    foods_by_id: Mapping[str, MealieFood],
    dataset: Dataset,
    corrections: Mapping[str, Correction],
) -> Resolved:
    """Decide what an ingredient is: a user correction wins, else the matcher."""
    correction = corrections.get(ingredient_key(ingredient))
    rejected: frozenset[str] = frozenset()
    if correction is not None:
        if correction.status == "ignored":
            return Resolved("ignored", None, confirmed=True)
        if correction.status == "no_season":
            return Resolved("no_season", None, confirmed=True)
        if correction.item_key:
            return Resolved("item", correction.item_key, confirmed=correction.confirmed)
        rejected = frozenset(correction.rejected)
    match = match_ingredient(ingredient, foods_by_id, dataset, rejected)
    if match.kind == "exact":
        return Resolved("item", match.item_key, confirmed=True)
    if match.kind == "fuzzy":
        return Resolved("item", match.item_key, confirmed=False)
    return Resolved("unreviewed", None, confirmed=False)


def score_recipe(
    recipe: MealieRecipe,
    resolutions: Sequence[Resolved],
    dataset: Dataset,
    month: int,
) -> RecipeScore | None:
    """Score a recipe; None when it has no produce ingredients."""
    months_by_key = {item.key: item.months for item in dataset.items}
    total = in_season = 0
    for resolved in resolutions:
        if resolved.kind == "no_season":
            total += 1
        elif resolved.kind == "item" and resolved.item_key in months_by_key:
            total += 1
            in_season += month in months_by_key[resolved.item_key]
    if total == 0:
        return None
    return RecipeScore(recipe.slug, recipe.name, in_season, total)


def rank(scores: Iterable[RecipeScore]) -> list[RecipeScore]:
    """Order by in-season ratio, then more produce ingredients, then name."""
    return sorted(
        scores,
        key=lambda s: (-(s.in_season / s.total), -s.total, s.name.casefold(), s.slug),
    )
