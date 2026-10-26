"""Persisted user corrections of ingredient matches."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .matching import normalise, strip_quantity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .mealie import MealieIngredient

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.corrections"

Status = Literal["item", "ignored", "no_season"]


@dataclass
class Correction:
    """
    What the user (or the matcher) decided about one ingredient.

    `item` with `item_key=None` means "no choice yet": the matcher decides, minus
    the `rejected` item keys.
    """

    status: Status
    item_key: str | None = None
    confirmed: bool = False
    rejected: list[str] = field(default_factory=list)


def ingredient_key(ingredient: MealieIngredient) -> str:
    """Stable key: the Mealie food when linked, else the normalised text."""
    if ingredient.food_id:
        return f"food:{ingredient.food_id}"
    text = strip_quantity(ingredient.text)
    # Text without Latin letters normalises to "": keep it distinguishable.
    return f"text:{normalise(text) or text.strip().casefold()}"


class CorrectionsStore:
    """Corrections kept in Home Assistant storage, keyed by `ingredient_key`."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._corrections: dict[str, Correction] = {}

    async def load(self) -> None:
        """Read the stored corrections."""
        data = await self._store.async_load() or {}
        self._corrections = {
            key: Correction(**raw) for key, raw in data.get("corrections", {}).items()
        }

    def get(self, key: str) -> Correction | None:
        """Return the correction for an ingredient key, if any."""
        return self._corrections.get(key)

    def all(self) -> dict[str, Correction]:
        """Return a copy of all corrections."""
        return dict(self._corrections)

    async def set(self, key: str, correction: Correction) -> None:
        """Store a correction and persist."""
        self._corrections[key] = correction
        await self._save()

    async def add_rejection(self, key: str, item_key: str) -> None:
        """Remember that `item_key` is not the right match for this ingredient."""
        correction = self._corrections.get(key) or Correction(status="item")
        if item_key not in correction.rejected:
            correction.rejected.append(item_key)
        await self.set(key, correction)

    async def async_remove(self) -> None:
        """Delete the stored corrections."""
        self._corrections = {}
        await self._store.async_remove()

    async def _save(self) -> None:
        await self._store.async_save(
            {"corrections": {k: asdict(c) for k, c in self._corrections.items()}}
        )
