"""Mealie REST client and discovery of Home Assistant's own Mealie credentials."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from aiohttp import ClientSession
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

MEALIE_DOMAIN = "mealie"
MODE_NONE = "none"
MODE_INTEGRATION = "integration"
MODE_MANUAL = "manual"

_PAGE_SIZE = 100
_DETAIL_CONCURRENCY = 5
_TIMEOUT = ClientTimeout(total=30)
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_HTTP_ERROR = 400


class MealieError(Exception):
    """Base class for Mealie problems."""


class MealieAuthError(MealieError):
    """The token was rejected."""


class MealieConnectionError(MealieError):
    """Mealie could not be reached or answered with an error."""


class MealieNotFoundError(MealieConnectionError):
    """The requested item does not exist (any more)."""


@dataclass(frozen=True)
class MealieFood:
    """A Mealie food with its aliases."""

    id: str
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class MealieIngredient:
    """One recipe ingredient: the linked food id (if any) and its text."""

    food_id: str | None
    text: str


@dataclass(frozen=True)
class MealieRecipe:
    """
    A Mealie recipe with its ingredients and display fields.

    `rating` and `favorite` are those of the API token's user: the `rating` in
    Mealie's recipe list is an average over all users and is ignored.
    """

    slug: str
    name: str
    ingredients: tuple[MealieIngredient, ...]
    updated: str = ""
    id: str = ""
    image: str | None = None
    description: str = ""
    tags: tuple[str, ...] = ()
    rating: float | None = None
    favorite: bool = False
    group_slug: str = ""


@dataclass(frozen=True)
class MealieCredentials:
    """Where and how to reach a Mealie server."""

    url: str
    token: str
    verify_ssl: bool


def _parse_ingredient(raw: Mapping[str, Any]) -> MealieIngredient | None:
    food = raw.get("food")
    if food:
        return MealieIngredient(food_id=food.get("id"), text=str(food["name"]).strip())
    text = str(raw.get("note") or raw.get("originalText") or "").strip()
    return MealieIngredient(food_id=None, text=text) if text else None


def image_url(base_url: str, recipe: MealieRecipe) -> str | None:
    """Return the browser URL of the recipe image, or None without an image."""
    if not recipe.image:
        return None
    root = base_url.rstrip("/")
    return f"{root}/api/media/recipes/{recipe.id}/images/original.webp?v={recipe.image}"


def recipe_url(base_url: str, recipe: MealieRecipe) -> str:
    """Return the Mealie web address that opens the recipe."""
    return f"{base_url.rstrip('/')}/g/{recipe.group_slug}/r/{recipe.slug}"


class MealieClient:
    """Minimal async client for the parts of Mealie's API this integration needs."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        """Create a client for `base_url` using a Mealie API token."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token = token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                json=body,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=_TIMEOUT,
            ) as response:
                if response.status in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
                    raise MealieAuthError(path)
                if response.status == _HTTP_NOT_FOUND:
                    raise MealieNotFoundError(path)
                if response.status >= _HTTP_ERROR:
                    msg = f"{path}: HTTP {response.status}"
                    raise MealieConnectionError(msg)
                return await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            msg = f"{path}: {err}"
            raise MealieConnectionError(msg) from err

    async def _paged(self, path: str) -> list[Mapping[str, Any]]:
        items: list[Mapping[str, Any]] = []
        page = 1
        while True:
            body = await self._request(
                "GET", path, params={"page": page, "perPage": _PAGE_SIZE}
            )
            if not isinstance(body, dict) or not isinstance(body.get("items"), list):
                msg = f"{path}: unexpected response"
                raise MealieConnectionError(msg)
            items.extend(body["items"])
            if page >= body.get("total_pages", 1):
                return items
            page += 1

    async def validate(self) -> None:
        """Raise a `MealieError` if the token is unusable."""
        await self._request("GET", "/api/users/self")

    async def get_foods(self) -> list[MealieFood]:
        """Return all foods with their aliases."""
        return [
            MealieFood(
                id=raw["id"],
                name=raw["name"],
                aliases=tuple(a["name"] for a in raw.get("aliases", [])),
            )
            for raw in await self._paged("/api/foods")
        ]

    async def _get_user_ratings(self) -> dict[str, tuple[float | None, bool]]:
        """Return the token user's (rating, favourite) per recipe id."""
        body = await self._request("GET", "/api/users/self/ratings")
        try:
            return {
                entry["recipeId"]: (entry.get("rating"), bool(entry.get("isFavorite")))
                for entry in body["ratings"]
            }
        except (KeyError, TypeError) as err:
            msg = f"unexpected ratings data: {err}"
            raise MealieConnectionError(msg) from err

    async def get_recipes(
        self, cached: Sequence[MealieRecipe] = ()
    ) -> list[MealieRecipe]:
        """
        Return all recipes with ingredients and display fields.

        Ingredients are fetched per recipe, but a recipe whose `dateUpdated` matches
        the one in `cached` reuses them. Display fields, ratings and favourites are
        refreshed on every call, because changing them does not touch `dateUpdated`.
        A recipe deleted meanwhile is skipped.
        """
        known = {recipe.slug: recipe for recipe in cached}
        group_slug = str(
            (await self._request("GET", "/api/users/self")).get("groupSlug")
        )
        ratings = await self._get_user_ratings()
        summaries = await self._paged("/api/recipes")
        semaphore = asyncio.Semaphore(_DETAIL_CONCURRENCY)

        async def detail(summary: Mapping[str, Any]) -> MealieRecipe | None:
            slug = summary["slug"]
            stamp = str(summary.get("dateUpdated") or summary.get("updatedAt") or "")
            rating, favorite = ratings.get(summary["id"], (None, False))
            display = {
                "id": summary["id"],
                "image": summary.get("image") or None,
                "description": str(summary.get("description") or ""),
                "tags": tuple(str(tag["name"]) for tag in summary.get("tags") or []),
                "rating": rating,
                "favorite": favorite,
                "group_slug": group_slug,
            }
            previous = known.get(slug)
            if previous is not None and stamp and previous.updated == stamp:
                return replace(previous, name=summary["name"], **display)
            async with semaphore:
                try:
                    raw = await self._request("GET", f"/api/recipes/{slug}")
                except MealieNotFoundError:
                    return None
            return MealieRecipe(
                slug=raw["slug"],
                name=raw["name"],
                ingredients=tuple(
                    ingredient
                    for entry in raw.get("recipeIngredient", [])
                    if (ingredient := _parse_ingredient(entry)) is not None
                ),
                updated=stamp,
                **display,
            )

        try:
            results = await asyncio.gather(*(detail(s) for s in summaries))
        except (KeyError, TypeError) as err:
            msg = f"unexpected recipe data: {err}"
            raise MealieConnectionError(msg) from err
        return [recipe for recipe in results if recipe is not None]

    async def add_food_alias(self, food_id: str, alias: str) -> None:
        """Add `alias` to a Mealie food unless it is already known."""
        food = await self._request("GET", f"/api/foods/{food_id}")
        known = {
            food["name"].casefold(),
            *(a["name"].casefold() for a in food["aliases"]),
        }
        if alias.casefold() in known:
            return
        food["aliases"] = [*food["aliases"], {"name": alias}]
        await self._request("PUT", f"/api/foods/{food_id}", body=food)


def discover_mealie_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return the loaded config entries of Home Assistant's own Mealie integration."""
    return [
        entry
        for entry in hass.config_entries.async_entries(MEALIE_DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def credentials_from_entry(entry: ConfigEntry) -> MealieCredentials:
    """Read URL, token and SSL setting from a core Mealie config entry."""
    return MealieCredentials(
        url=entry.data[CONF_HOST],
        token=entry.data[CONF_API_TOKEN],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )


def credentials_for(
    hass: HomeAssistant, mealie: Mapping[str, Any]
) -> MealieCredentials | None:
    """
    Resolve the credentials for the entry's Mealie settings, live.

    Returns None when Mealie is skipped. Raises `MealieConnectionError` when the
    reused Home Assistant Mealie entry no longer exists.
    """
    mode = mealie.get("mode", MODE_NONE)
    if mode == MODE_MANUAL:
        return MealieCredentials(
            url=mealie["url"],
            token=mealie["token"],
            verify_ssl=mealie.get("verify_ssl", True),
        )
    if mode == MODE_INTEGRATION:
        entry = hass.config_entries.async_get_entry(mealie["entry_id"])
        if entry is None or entry.domain != MEALIE_DOMAIN:
            msg = "the reused Mealie integration entry no longer exists"
            raise MealieConnectionError(msg)
        return credentials_from_entry(entry)
    return None


def client_for(hass: HomeAssistant, credentials: MealieCredentials) -> MealieClient:
    """Create a client that uses Home Assistant's shared HTTP session."""
    session = async_get_clientsession(hass, verify_ssl=credentials.verify_ssl)
    return MealieClient(session, credentials.url, credentials.token)
