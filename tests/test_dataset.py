"""Tests for the bundled seasonal dataset and its loader."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from custom_components.seasonal_groceries.dataset import (
    BUNDLED_PATH,
    Dataset,
    Item,
    load_dataset,
)

if TYPE_CHECKING:
    from pathlib import Path


def _raw() -> dict:
    return json.loads(BUNDLED_PATH.read_text(encoding="utf-8"))


def _write(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "produce.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _item(dataset: Dataset, key: str) -> Item:
    return next(i for i in dataset.items if i.key == key)


def test_loads_bundled_file() -> None:
    dataset = load_dataset()
    assert len(dataset.items) >= 70
    assert {"calendar", "pesticides"} <= set(dataset.credits)


def test_rejects_duplicate_keys(tmp_path: Path) -> None:
    raw = _raw()
    raw["items"].append(dict(raw["items"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(_write(tmp_path, raw))


def test_rejects_month_outside_1_12(tmp_path: Path) -> None:
    raw = _raw()
    raw["items"][0]["months"] = [0, 13]
    with pytest.raises(ValueError, match="month"):
        load_dataset(_write(tmp_path, raw))


def test_every_item_has_nl_and_en_name() -> None:
    for item in load_dataset().items:
        assert item.names["nl"].strip(), item.key
        assert item.names["en"].strip(), item.key


def test_item_name_falls_back_to_english() -> None:
    item = _item(load_dataset(), "tomaat")
    assert item.name("nl") == "tomaat"
    assert item.name("en") == "tomato"
    assert item.name("de") == "tomato"


def test_credits_name_voedingscentrum_and_pan() -> None:
    credit_map = load_dataset().credits
    assert {"Voedingscentrum", "Velt", "Bionext"} <= set(
        credit_map["calendar"].organisations
    )
    pesticides = credit_map["pesticides"]
    assert any("PAN Netherlands" in o for o in pesticides.organisations)
    assert "NVWA" in " ".join(pesticides.organisations)
    assert "2021" in pesticides.note
    assert "2023" in pesticides.note


def test_cutoffs_per_type() -> None:
    cutoffs = load_dataset().cutoffs
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
    assert _item(load_dataset(), key).residues == residues


def test_unknown_residues_is_none() -> None:
    assert _item(load_dataset(), "aardpeer").residues is None


def test_calendar_spot_checks() -> None:
    dataset = load_dataset()
    assert _item(dataset, "prei").months == frozenset(range(1, 13))
    assert _item(dataset, "pompoen").months == frozenset({1, 2, 3, 4, 8, 9, 10, 11, 12})
    assert _item(dataset, "asperge").months == frozenset({4, 5, 6})
    assert _item(dataset, "appel").type == "fruit"
    assert _item(dataset, "tomaat").type == "vegetable"
