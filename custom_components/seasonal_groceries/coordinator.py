"""Coordinator: fetch Mealie data, rank recipes and build the review queue."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, Language
from .corrections import ingredient_key
from .dataset import Dataset, load_dataset
from .matching import match_ingredient
from .mealie import MealieError, client_for, credentials_for
from .scoring import RecipeScore, rank, resolve, score_recipe

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .corrections import CorrectionsStore
    from .mealie import MealieFood, MealieRecipe

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=30)


@dataclass(frozen=True)
class QueueEntry:
    """An ingredient waiting for the user to confirm or fix its match."""

    ingredient_key: str
    text: str
    current_item_key: str | None
    suggestions: tuple[str, ...]


@dataclass(frozen=True)
class CoordinatorData:
    """Everything the cards need from Mealie."""

    recipes: list[RecipeScore] = field(default_factory=list)
    queue: list[QueueEntry] = field(default_factory=list)
    mealie_configured: bool = False


class SeasonalGroceriesCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Fetches recipes (when Mealie is configured) and keeps the ranking current."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, corrections: CorrectionsStore
    ) -> None:
        """Create the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.corrections = corrections
        self._foods: dict[str, MealieFood] = {}
        self._recipes: list[MealieRecipe] = []
        self._datasets: dict[Language, Dataset] = {}
        self._unsub_month: Callable[[], None] | None = None

    @property
    def settings(self) -> dict[str, Any]:
        """Entry data overlaid with options."""
        assert self.config_entry is not None  # noqa: S101
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def language(self) -> Language:
        """The grocery language."""
        return Language(self.settings.get("language", Language.EN))

    @property
    def dataset(self) -> Dataset:
        """The seasonal dataset in the grocery language."""
        language = self.language
        if language not in self._datasets:
            self._datasets[language] = load_dataset(language)
        return self._datasets[language]

    @property
    def month(self) -> int:
        """The current month in Home Assistant's timezone."""
        return dt_util.now().month

    async def _async_update_data(self) -> CoordinatorData:
        mealie = self.settings.get("mealie", {"mode": "none"})
        try:
            credentials = credentials_for(self.hass, mealie)
            if credentials is None:
                self._foods, self._recipes = {}, []
                return self._build(mealie_configured=False)
            client = client_for(self.hass, credentials)
            foods = await client.get_foods()
            recipes = await client.get_recipes()
        except MealieError as err:
            msg = f"Mealie unavailable: {err}"
            raise UpdateFailed(msg) from err
        self._foods = {food.id: food for food in foods}
        self._recipes = recipes
        return self._build(mealie_configured=True)

    def async_recompute(self) -> None:
        """Rebuild the ranking from cached Mealie data (corrections, new month)."""
        configured = self.data.mealie_configured if self.data else False
        self.async_set_updated_data(self._build(mealie_configured=configured))

    def _build(self, *, mealie_configured: bool) -> CoordinatorData:
        dataset, month = self.dataset, self.month
        corrections = self.corrections.all()
        cache: dict[str, tuple[Any, Any]] = {}
        scores: list[RecipeScore] = []
        queue: dict[str, QueueEntry] = {}
        for recipe in self._recipes:
            resolutions = []
            for ingredient in recipe.ingredients:
                key = ingredient_key(ingredient)
                if key not in cache:
                    cache[key] = (
                        ingredient,
                        resolve(ingredient, self._foods, dataset, corrections),
                    )
                resolved = cache[key][1]
                resolutions.append(resolved)
                if key not in queue and self._needs_review(resolved):
                    queue[key] = self._queue_entry(
                        key, ingredient, resolved, corrections
                    )
            if (score := score_recipe(recipe, resolutions, dataset, month)) is not None:
                scores.append(score)
        ordered_queue = sorted(
            queue.values(),
            key=lambda e: (e.current_item_key is None, e.text.casefold()),
        )
        return CoordinatorData(rank(scores), ordered_queue, mealie_configured)

    @staticmethod
    def _needs_review(resolved: Any) -> bool:
        return resolved.kind == "unreviewed" or (
            resolved.kind == "item" and not resolved.confirmed
        )

    def _queue_entry(
        self, key: str, ingredient: Any, resolved: Any, corrections: Any
    ) -> QueueEntry:
        correction = corrections.get(key)
        rejected = frozenset(correction.rejected) if correction else frozenset()
        match = match_ingredient(ingredient, self._foods, self.dataset, rejected)
        suggestions = match.suggestions
        if resolved.item_key and resolved.item_key not in suggestions:
            suggestions = (resolved.item_key, *suggestions)
        return QueueEntry(key, ingredient.text, resolved.item_key, suggestions)

    def async_start_month_listener(self) -> None:
        """Recompute shortly after midnight on the 1st (Home Assistant's timezone)."""
        self.async_stop_month_listener()
        self._unsub_month = async_track_time_change(
            self.hass, self._handle_midnight, hour=0, minute=0, second=5
        )

    def async_stop_month_listener(self) -> None:
        """Stop the month rollover listener."""
        if self._unsub_month is not None:
            self._unsub_month()
            self._unsub_month = None

    def _handle_midnight(self, now: Any) -> None:
        if dt_util.as_local(now).day == 1:
            self.async_recompute()
