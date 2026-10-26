"""Match recipe ingredients to seasonal items, by name, alias and fuzzy similarity."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .dataset import Dataset
    from .mealie import MealieFood, MealieIngredient

MatchKind = Literal["exact", "fuzzy", "none"]

FUZZY_THRESHOLD = 0.75
_MAX_SUGGESTIONS = 3
_MIN_SUGGESTION_SCORE = 0.5
_MIN_TOKEN_LENGTH = 4
# Plural endings that turn a known name into an exact match ("ui" -> "uien").
_PLURAL_SUFFIXES = ("s", "es", "en", "n")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class Match:
    """
    Outcome of matching one ingredient.

    `suggestions` holds up to three item keys, best first; never scores.
    """

    kind: MatchKind
    item_key: str | None
    suggestions: tuple[str, ...]


def normalise(text: str) -> str:
    """Lowercase, fold accents, replace punctuation by single spaces."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _NON_ALNUM.sub(" ", folded.lower()).strip()


def _is_plural_of(text: str, name: str) -> bool:
    return any(text == name + suffix for suffix in _PLURAL_SUFFIXES)


def _variants(
    ingredient: MealieIngredient, foods_by_id: Mapping[str, MealieFood]
) -> set[str]:
    """Every normalised spelling Mealie knows for this ingredient."""
    texts = [ingredient.text]
    food = foods_by_id.get(ingredient.food_id) if ingredient.food_id else None
    if food:
        texts += [food.name, *food.aliases]
    return {normalised for text in texts if (normalised := normalise(text))}


def _item_names(dataset: Dataset, rejected: frozenset[str]) -> dict[str, set[str]]:
    return {
        item.key: {normalise(n) for n in (item.name, *item.aliases) if normalise(n)}
        for item in dataset.items
        if item.key not in rejected
    }


def _tokens(variants: Iterable[str]) -> set[str]:
    return {
        word
        for variant in variants
        for word in variant.split()
        if len(word) >= _MIN_TOKEN_LENGTH
    }


def _score(candidates: set[str], names: set[str]) -> float:
    return max(
        (SequenceMatcher(None, c, n).ratio() for c in candidates for n in names),
        default=0.0,
    )


def match_ingredient(
    ingredient: MealieIngredient,
    foods_by_id: Mapping[str, MealieFood],
    dataset: Dataset,
    rejected: frozenset[str] = frozenset(),
) -> Match:
    """
    Match an ingredient against the (single-language) dataset.

    Exact: a Mealie name or alias equals an item name or alias, or is its plural.
    Fuzzy: the best similarity of any spelling or word reaches the threshold.
    Rejected item keys are never returned or suggested.
    """
    variants = _variants(ingredient, foods_by_id)
    if not variants:
        return Match("none", None, ())
    names = _item_names(dataset, rejected)

    for key, item_names in names.items():
        if any(
            v in item_names or any(_is_plural_of(v, n) for n in item_names)
            for v in variants
        ):
            return Match("exact", key, (key,))

    candidates = variants | _tokens(variants)
    scored = sorted(
        ((_score(candidates, item_names), key) for key, item_names in names.items()),
        key=lambda pair: (-pair[0], pair[1]),
    )
    suggestions = tuple(
        key
        for score, key in scored[:_MAX_SUGGESTIONS]
        if score >= _MIN_SUGGESTION_SCORE
    )
    if scored and scored[0][0] >= FUZZY_THRESHOLD:
        return Match("fuzzy", scored[0][1], suggestions)
    return Match("none", None, suggestions)
