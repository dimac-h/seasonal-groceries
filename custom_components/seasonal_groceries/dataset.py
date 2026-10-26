"""Bundled seasonal-produce dataset: calendar, pesticides, cutoffs and credits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

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


_MONTHS = range(1, 13)


def _parse_item(raw: Mapping[str, Any]) -> Item:
    key = raw.get("key")
    if not isinstance(key, str) or not key:
        msg = "item without key"
        raise ValueError(msg)
    names = raw.get("names", {})
    for language in LANGUAGES:
        if not str(names.get(language, "")).strip():
            msg = f"{key}: missing {language} name"
            raise ValueError(msg)
    if raw.get("type") not in _TYPES:
        msg = f"{key}: type must be one of {_TYPES}"
        raise ValueError(msg)
    months = raw.get("months", [])
    if not months or not all(isinstance(m, int) and m in _MONTHS for m in months):
        msg = f"{key}: month must be an integer from 1 to 12"
        raise ValueError(msg)
    residues = raw.get("residues")
    if residues is not None and not isinstance(residues, (int, float)):
        msg = f"{key}: residues must be a number or null"
        raise ValueError(msg)
    aliases = {lang: tuple(values) for lang, values in raw.get("aliases", {}).items()}
    return Item(
        key=key,
        names=dict(names),
        type=raw["type"],
        months=frozenset(months),
        residues=None if residues is None else float(residues),
        aliases=aliases,
    )


def _parse_cutoffs(raw: Mapping[str, Any]) -> dict[ProduceType, Cutoffs]:
    result: dict[ProduceType, Cutoffs] = {}
    for produce_type in _TYPES:
        entry = raw[produce_type]
        cutoffs = Cutoffs(
            green_max=float(entry["green_max"]),
            orange_max=float(entry["orange_max"]),
            provisional=bool(entry.get("provisional", False)),
        )
        if cutoffs.green_max >= cutoffs.orange_max:
            msg = f"{produce_type}: cutoffs out of order"
            raise ValueError(msg)
        result[produce_type] = cutoffs
    return result


def load_dataset(path: Path | None = None) -> Dataset:
    """Load and validate a dataset file (the bundled one by default)."""
    raw = json.loads((path or BUNDLED_PATH).read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        msg = "unsupported schema_version"
        raise ValueError(msg)

    items = tuple(_parse_item(entry) for entry in raw["items"])
    keys = [item.key for item in items]
    if len(keys) != len(set(keys)):
        msg = "duplicate item keys"
        raise ValueError(msg)

    credit_map = {
        name: Credit(
            label=entry["label"],
            organisations=tuple(entry["organisations"]),
            url=entry["url"],
            note=entry["note"],
        )
        for name, entry in raw["credits"].items()
    }
    return Dataset(
        items=items,
        cutoffs=_parse_cutoffs(raw["cutoffs"]),
        credits=credit_map,
        data_as_of=raw["data_as_of"],
    )
