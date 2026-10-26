"""Config flow for the Seasonal Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class SeasonalGroceriesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seasonal Groceries."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Seasonal Groceries", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
