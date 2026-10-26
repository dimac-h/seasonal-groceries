"""Season sorting and pesticide bands (pure functions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .dataset import Cutoffs, Dataset, Item, ProduceType

Band = Literal["green", "orange", "red", "unknown"]


@dataclass(frozen=True)
class Row:
    """One produce item as shown in a list, for one month."""

    item: Item
    band: Band
    in_season: bool


def band_for(item: Item, cutoffs: Mapping[ProduceType, Cutoffs]) -> Band:
    """Pesticide band of an item; a value on a boundary falls in the lower band."""
    if item.residues is None:
        return "unknown"
    limits = cutoffs[item.type]
    if item.residues <= limits.green_max:
        return "green"
    if item.residues <= limits.orange_max:
        return "orange"
    return "red"


def rows(
    dataset: Dataset,
    produce_type: ProduceType,
    month: int,
    *,
    only_in_season: bool = False,
    max_rows: int | None = None,
) -> list[Row]:
    """Items of one type: in season first, fewest residues first, unknown last."""
    result = [
        Row(
            item=item,
            band=band_for(item, dataset.cutoffs),
            in_season=month in item.months,
        )
        for item in dataset.items
        if item.type == produce_type
    ]
    if only_in_season:
        result = [row for row in result if row.in_season]
    result.sort(
        key=lambda row: (
            not row.in_season,
            row.item.residues is None,
            row.item.residues if row.item.residues is not None else 0.0,
            row.item.key,
        )
    )
    return result if max_rows is None else result[:max_rows]
