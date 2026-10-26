"""Tests for the bundled seasonal dataset and its loader."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.seasonal_groceries.const import Language
from custom_components.seasonal_groceries.dataset import (
    BUNDLED_PATH,
    Dataset,
    Item,
    load_dataset,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

ALL_LANGUAGES = list(Language)


def _edited_copy(tmp_path: Path, change: Callable[[dict[str, Any]], object]) -> Path:
    document = json.loads(BUNDLED_PATH.read_text(encoding="utf-8"))
    change(document)
    target = tmp_path / "produce.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def _item(dataset: Dataset, key: str) -> Item:
    return next(i for i in dataset.items if i.key == key)


@pytest.mark.parametrize("language", ALL_LANGUAGES)
def test_loads_bundled_file_for_every_language(language: Language) -> None:
    dataset = load_dataset(language)
    assert len(dataset.items) >= 70
    assert {"calendar", "pesticides"} <= set(dataset.credits)
    assert all(item.name.strip() for item in dataset.items)


def test_every_item_has_a_name_in_every_language() -> None:
    document = json.loads(BUNDLED_PATH.read_text(encoding="utf-8"))
    for item in document["items"]:
        for language in Language:
            assert item["names"].get(language.value, "").strip(), (
                item["key"],
                language,
            )


def test_names_come_from_the_requested_language() -> None:
    assert _item(load_dataset(Language.NL), "tomaat").name == "tomaat"
    assert _item(load_dataset(Language.EN), "tomaat").name == "tomato"


def test_aliases_come_from_the_requested_language() -> None:
    assert "rode kool" in _item(load_dataset(Language.NL), "rodekool").aliases
    assert "zucchini" in _item(load_dataset(Language.EN), "courgette").aliases
    assert "zucchini" not in _item(load_dataset(Language.NL), "courgette").aliases


def test_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = _edited_copy(tmp_path, lambda d: d["items"].append(dict(d["items"][0])))
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(Language.EN, path)


def test_rejects_month_outside_1_12(tmp_path: Path) -> None:
    path = _edited_copy(tmp_path, lambda d: d["items"][0].update(months=[0, 13]))
    with pytest.raises(ValueError, match="month"):
        load_dataset(Language.EN, path)


def test_rejects_item_without_a_name_in_the_requested_language(
    tmp_path: Path,
) -> None:
    path = _edited_copy(tmp_path, lambda d: d["items"][0]["names"].pop("en"))
    with pytest.raises(ValueError, match="en"):
        load_dataset(Language.EN, path)
    assert load_dataset(Language.NL, path)


def test_credits_name_voedingscentrum_and_pan() -> None:
    credit_map = load_dataset(Language.EN).credits
    assert {"Voedingscentrum", "Velt", "Bionext"} <= set(
        credit_map["calendar"].organisations
    )
    pesticides = credit_map["pesticides"]
    assert any("PAN Netherlands" in o for o in pesticides.organisations)
    assert "NVWA" in " ".join(pesticides.organisations)
    assert "2021" in pesticides.note
    assert "2023" in pesticides.note


def test_cutoffs_per_type() -> None:
    cutoffs = load_dataset(Language.EN).cutoffs
    assert (cutoffs["vegetable"].green_max, cutoffs["vegetable"].orange_max) == (
        0.4,
        1.8,
    )
    assert not cutoffs["vegetable"].provisional
    assert (cutoffs["fruit"].green_max, cutoffs["fruit"].orange_max) == (1.8, 3.0)
    assert cutoffs["fruit"].provisional


@pytest.mark.parametrize(
    ("key", "residues"),
    [
        ("rode-biet", 0.1),
        ("spruiten", 1.9),
        ("appel", 3.4),
        ("peer", 3.3),
        ("asperge", 0.0),
        ("pompoen", 0.4),
        ("wortel", 1.6),
        ("prei", 1.8),
        ("kropsla", 3.6),
        ("aardbei", 3.9),
        ("blauwe-bes", 2.0),
        ("pruim", 1.8),
        ("rodekool", 0.3),
        ("tomaat", 1.1),
    ],
)
def test_pan_residues(key: str, residues: float) -> None:
    assert _item(load_dataset(Language.EN), key).residues == residues


def test_unknown_residues_is_none() -> None:
    assert _item(load_dataset(Language.EN), "aardpeer").residues is None


def test_calendar_spot_checks() -> None:
    dataset = load_dataset(Language.EN)
    assert _item(dataset, "prei").months == frozenset(range(1, 13))
    assert _item(dataset, "pompoen").months == frozenset({1, 2, 3, 4, 8, 9, 10, 11, 12})
    assert _item(dataset, "asperge").months == frozenset({4, 5, 6})
    assert _item(dataset, "appel").type == "fruit"
    assert _item(dataset, "tomaat").type == "vegetable"
