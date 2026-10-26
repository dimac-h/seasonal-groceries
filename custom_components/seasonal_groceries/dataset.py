"""The bundled seasonal-produce dataset: calendar, pesticide levels, cutoffs and credits."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ProduceType = Literal["vegetable", "fruit"]

BUNDLED_PATH = Path(__file__).parent / "data" / "produce.json"
LANGUAGES = ("nl", "en")
_TYPES = ("vegetable", "fruit")


@dataclass(frozen=True)
class Item:
    """One vegetable or fruit."""

    key: str
    names: Mapping[str, str]
    type: ProduceType
    months: frozenset[int]
    residues: float | None
    aliases: Mapping[str, tuple[str, ...]]

    def name(self, language: str) -> str:
        """Return the name in `language`, falling back to English."""
        return self.names.get(language) or self.names["en"]


@dataclass(frozen=True)
class Cutoffs:
    """Upper bounds of the green and orange pesticide bands (inclusive)."""

    green_max: float
    orange_max: float
    provisional: bool


@dataclass(frozen=True)
class Credit:
    """Where a part of the data comes from."""

    label: str
    organisations: tuple[str, ...]
    url: str
    note: str


@dataclass(frozen=True)
class Dataset:
    """Everything the integration knows about seasonal produce."""

    items: tuple[Item, ...]
    cutoffs: Mapping[ProduceType, Cutoffs]
    credits: Mapping[str, Credit]
    data_as_of: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _parse_item(raw: Mapping[str, Any]) -> Item:
    key = raw.get("key")
    _require(isinstance(key, str) and key != "", "item without key")
    names = raw.get("names", {})
    for language in LANGUAGES:
        _require(bool(str(names.get(language, "")).strip()), f"{key}: missing {language} name")
    _require(raw.get("type") in _TYPES, f"{key}: type must be one of {_TYPES}")
    months = raw.get("months", [])
    _require(
        bool(months) and all(isinstance(m, int) and 1 <= m <= 12 for m in months),
        f"{key}: month must be an integer from 1 to 12",
    )
    residues = raw.get("residues")
    _require(residues is None or isinstance(residues, (int, float)), f"{key}: residues must be a number or null")
    aliases = {lang: tuple(values) for lang, values in raw.get("aliases", {}).items()}
    return Item(
        key=key,
        names=dict(names),
        type=raw["type"],
        months=frozenset(months),
        residues=None if residues is None else float(residues),
        aliases=aliases,
    )


def load_dataset(path: Path | None = None) -> Dataset:
    """Load and validate a dataset file (the bundled one by default)."""
    raw = json.loads((path or BUNDLED_PATH).read_text(encoding="utf-8"))
    _require(raw.get("schema_version") == 1, "unsupported schema_version")

    items = tuple(_parse_item(entry) for entry in raw["items"])
    keys = [item.key for item in items]
    _require(len(keys) == len(set(keys)), "duplicate item keys")

    cutoffs = {}
    for produce_type in _TYPES:
        entry = raw["cutoffs"][produce_type]
        cutoffs[produce_type] = Cutoffs(
            green_max=float(entry["green_max"]),
            orange_max=float(entry["orange_max"]),
            provisional=bool(entry.get("provisional", False)),
        )
        _require(cutoffs[produce_type].green_max < cutoffs[produce_type].orange_max, f"{produce_type}: cutoffs out of order")

    credits = {
        name: Credit(
            label=entry["label"],
            organisations=tuple(entry["organisations"]),
            url=entry["url"],
            note=entry["note"],
        )
        for name, entry in raw["credits"].items()
    }
    return Dataset(items=items, cutoffs=cutoffs, credits=credits, data_as_of=raw["data_as_of"])
