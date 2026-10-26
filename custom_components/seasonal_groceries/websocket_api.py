"""WebSocket commands used by the Seasonal Groceries cards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import ACTIONS
from .season import rows

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import SeasonalGroceriesCoordinator

PRODUCE_TYPES = ["vegetable", "fruit"]


def _coordinator(hass: HomeAssistant) -> SeasonalGroceriesCoordinator | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    return None


def _with_coordinator(handler: Any) -> Any:
    """Reply with an error when the integration is not loaded."""

    async def wrapper(
        hass: HomeAssistant, connection: Any, msg: dict[str, Any]
    ) -> None:
        coordinator = _coordinator(hass)
        if coordinator is None:
            connection.send_error(
                msg["id"], "not_loaded", "Seasonal Groceries is not loaded"
            )
            return
        try:
            await handler(connection, msg, coordinator)
        except HomeAssistantError as err:
            connection.send_error(msg["id"], "action_failed", str(err))

    return wrapper


def _mealie_status(coordinator: SeasonalGroceriesCoordinator) -> dict[str, bool]:
    return {
        "mealie_configured": coordinator.mealie_configured,
        "mealie_ok": coordinator.last_update_success,
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/items",
        vol.Required("produce_type"): vol.In(PRODUCE_TYPES),
        vol.Required("mode"): vol.In(["now", "calendar"]),
        vol.Optional("max_rows"): vol.All(int, vol.Range(min=1)),
    }
)
@websocket_api.async_response
@_with_coordinator
async def ws_items(
    connection: Any,
    msg: dict[str, Any],
    coordinator: SeasonalGroceriesCoordinator,
) -> None:
    """Return seasonal items for the current month."""
    dataset, month = coordinator.dataset, coordinator.month
    result = rows(
        dataset,
        msg["produce_type"],
        month,
        only_in_season=msg["mode"] == "now",
        max_rows=msg.get("max_rows"),
    )
    connection.send_result(
        msg["id"],
        {
            "month": month,
            "data_as_of": dataset.data_as_of,
            "rows": [
                {
                    "key": row.item.key,
                    "name": row.item.name,
                    "type": row.item.type,
                    "months": sorted(row.item.months),
                    "residues": row.item.residues,
                    "band": row.band,
                    "in_season": row.in_season,
                }
                for row in result
            ],
            "credits": {
                name: {
                    "label": credit.label,
                    "organisations": list(credit.organisations),
                    "url": credit.url,
                    "note": credit.note,
                }
                for name, credit in dataset.credits.items()
            },
            "provisional_cutoffs": [
                produce_type
                for produce_type, cutoffs in dataset.cutoffs.items()
                if cutoffs.provisional
            ],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recipes",
        vol.Optional("limit"): vol.All(int, vol.Range(min=1)),
    }
)
@websocket_api.async_response
@_with_coordinator
async def ws_recipes(
    connection: Any,
    msg: dict[str, Any],
    coordinator: SeasonalGroceriesCoordinator,
) -> None:
    """Return Mealie recipes ranked by how seasonal they are."""
    recipes = coordinator.data.recipes if coordinator.data else []
    connection.send_result(
        msg["id"],
        {
            "recipes": [
                {
                    "slug": r.slug,
                    "name": r.name,
                    "in_season": r.in_season,
                    "total": r.total,
                }
                for r in recipes[: msg.get("limit")]
            ],
            **_mealie_status(coordinator),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/review_queue"})
@websocket_api.async_response
@_with_coordinator
async def ws_review_queue(
    connection: Any,
    msg: dict[str, Any],
    coordinator: SeasonalGroceriesCoordinator,
) -> None:
    """Return the ingredients waiting for review."""
    queue = coordinator.data.queue if coordinator.data else []
    connection.send_result(
        msg["id"],
        {
            "entries": [
                {
                    "ingredient_key": e.ingredient_key,
                    "text": e.text,
                    "current_item_key": e.current_item_key,
                    "suggestions": list(e.suggestions),
                }
                for e in queue
            ],
            **_mealie_status(coordinator),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@websocket_api.async_response
@_with_coordinator
async def ws_subscribe(
    connection: Any,
    msg: dict[str, Any],
    coordinator: SeasonalGroceriesCoordinator,
) -> None:
    """Tell the card whenever the data changed (open to every user)."""

    @callback
    def forward() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {}))

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(forward)
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/item_options"})
@websocket_api.async_response
@_with_coordinator
async def ws_item_options(
    connection: Any,
    msg: dict[str, Any],
    coordinator: SeasonalGroceriesCoordinator,
) -> None:
    """Return every seasonal item, for the Change dropdown."""
    options = sorted(coordinator.dataset.items, key=lambda i: i.name.casefold())
    connection.send_result(
        msg["id"],
        {"options": [{"key": i.key, "name": i.name, "type": i.type} for i in options]},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/review_resolve",
        vol.Required("ingredient_key"): str,
        vol.Required("action"): vol.In(ACTIONS),
        vol.Optional("item_key"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@_with_coordinator
async def ws_review_resolve(
    connection: Any,
    msg: dict[str, Any],
    coordinator: SeasonalGroceriesCoordinator,
) -> None:
    """Apply a review action to one ingredient."""
    await coordinator.async_resolve_entry(
        msg["ingredient_key"], msg["action"], msg.get("item_key")
    )
    connection.send_result(msg["id"], {})


def async_register_commands(hass: HomeAssistant) -> None:
    """Register all WebSocket commands."""
    for command in (
        ws_items,
        ws_recipes,
        ws_review_queue,
        ws_item_options,
        ws_subscribe,
        ws_review_resolve,
    ):
        websocket_api.async_register_command(hass, command)
