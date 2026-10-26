"""Tests for season sorting and pesticide bands."""

from __future__ import annotations

import pytest

from custom_components.seasonal_groceries.dataset import Dataset, Item, load_dataset
from custom_components.seasonal_groceries.season import band_for, rows


def _item(
    key: str, residues: float | None, months: set[int], produce_type: str = "vegetable"
) -> Item:
    return Item(
        key=key,
        names={"nl": key, "en": key},
        type=produce_type,  # type: ignore[arg-type]
        months=frozenset(months),
        residues=residues,
        aliases={},
    )


def _dataset(*items: Item) -> Dataset:
    real = load_dataset()
    return Dataset(
        items=tuple(items),
        cutoffs=real.cutoffs,
        credits=real.credits,
        data_as_of=real.data_as_of,
    )


CUTOFFS = load_dataset().cutoffs


@pytest.mark.parametrize(
    ("residues", "band"),
    [
        (0.0, "green"),
        (0.4, "green"),
        (0.5, "orange"),
        (1.8, "orange"),
        (1.9, "red"),
        (3.6, "red"),
    ],
)
def test_band_vegetable_boundaries(residues: float, band: str) -> None:
    assert band_for(_item("x", residues, {1}), CUTOFFS) == band


@pytest.mark.parametrize(
    ("residues", "band"),
    [(1.8, "green"), (1.9, "orange"), (3.0, "orange"), (3.1, "red")],
)
def test_band_fruit_boundaries(residues: float, band: str) -> None:
    assert band_for(_item("x", residues, {1}, "fruit"), CUTOFFS) == band


def test_band_unknown_for_none() -> None:
    assert band_for(_item("x", None, {1}), CUTOFFS) == "unknown"


def test_rows_sort_order() -> None:
    dataset = _dataset(
        _item("unknown-in", None, {10}),
        _item("red-in", 1.9, {10}),
        _item("green-in", 0.1, {10}),
        _item("orange-in", 1.0, {10}),
        _item("green-out", 0.0, {3}),
    )
    result = rows(dataset, "vegetable", 10)
    assert [r.item.key for r in result] == [
        "green-in",
        "orange-in",
        "red-in",
        "unknown-in",
        "green-out",
    ]
    assert [r.in_season for r in result] == [True, True, True, True, False]
    assert [r.band for r in result] == ["green", "orange", "red", "unknown", "green"]


def test_rows_ties_sorted_by_key() -> None:
    dataset = _dataset(_item("b", 0.1, {10}), _item("a", 0.1, {10}))
    assert [r.item.key for r in rows(dataset, "vegetable", 10)] == ["a", "b"]


def test_rows_filter_by_type() -> None:
    dataset = _dataset(_item("veg", 0.1, {10}), _item("fr", 0.1, {10}, "fruit"))
    assert [r.item.key for r in rows(dataset, "fruit", 10)] == ["fr"]


def test_rows_year_boundary() -> None:
    dataset = _dataset(_item("winter", 0.1, {11, 12, 1, 2}))
    assert rows(dataset, "vegetable", 12)[0].in_season
    assert rows(dataset, "vegetable", 1)[0].in_season
    assert not rows(dataset, "vegetable", 6)[0].in_season


def test_rows_max_rows_cuts_after_sorting() -> None:
    dataset = _dataset(
        _item("late", 2.0, {10}), _item("early", 0.1, {10}), _item("mid", 1.0, {10})
    )
    assert [r.item.key for r in rows(dataset, "vegetable", 10, max_rows=2)] == [
        "early",
        "mid",
    ]


def test_only_in_season_excludes_others() -> None:
    dataset = _dataset(_item("in", 1.0, {10}), _item("out", 0.0, {3}))
    assert [
        r.item.key for r in rows(dataset, "vegetable", 10, only_in_season=True)
    ] == ["in"]


def test_real_dataset_october_vegetables_start_with_green_in_season() -> None:
    result = rows(load_dataset(), "vegetable", 10, only_in_season=True)
    assert result
    assert result[0].band == "green"
    known = [r.item.residues for r in result if r.item.residues is not None]
    assert known == sorted(known)
    unknown_positions = [i for i, r in enumerate(result) if r.band == "unknown"]
    assert unknown_positions == list(
        range(len(result) - len(unknown_positions), len(result))
    )
