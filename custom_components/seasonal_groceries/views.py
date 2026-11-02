"""HTTP view that serves Mealie recipe images through Home Assistant."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState

from .const import DOMAIN
from .mealie import MealieError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

IMAGE_PATH = f"/api/{DOMAIN}/recipe_image"
_IMAGE_CACHE = "private, max-age=86400"


def image_path(slug: str) -> str:
    """Return the unsigned path that serves the image of a recipe."""
    return f"{IMAGE_PATH}/{slug}"


class RecipeImageView(HomeAssistantView):
    """
    Proxy a recipe image from Mealie.

    Browsers cannot always reach the address Home Assistant uses for Mealie, but they
    can reach Home Assistant. The cards request a signed path, because an `<img>`
    cannot send an authorization header.
    """

    url = f"{IMAGE_PATH}/{{slug}}"
    name = f"api:{DOMAIN}:recipe_image"

    async def get(self, request: web.Request, slug: str) -> web.Response:
        """Return the recipe's image."""
        hass: HomeAssistant = request.app[KEY_HASS]
        coordinator = next(
            (
                entry.runtime_data
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.state is ConfigEntryState.LOADED
            ),
            None,
        )
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        try:
            image = await coordinator.async_recipe_image(slug)
        except MealieError:
            return web.Response(status=HTTPStatus.BAD_GATEWAY)
        if image is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        body, content_type = image
        return web.Response(
            body=body,
            content_type=content_type,
            headers={"Cache-Control": _IMAGE_CACHE},
        )
