"""Config flow and options flow for the Seasonal Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, Language, language_for
from .mealie import (
    MODE_INTEGRATION,
    MODE_MANUAL,
    MODE_NONE,
    MealieAuthError,
    MealieClient,
    MealieError,
    discover_mealie_entries,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.data_entry_flow import FlowResult

CONF_LANGUAGE = "language"
CONF_MEALIE = "mealie"
CONF_WRITE_BACK = "write_back_aliases"


def _language_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[language.value for language in Language],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_LANGUAGE,
        )
    )


class SeasonalGroceriesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seasonal Groceries."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._language = Language.EN

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SeasonalGroceriesOptionsFlow:
        """Return the options flow."""
        return SeasonalGroceriesOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for the grocery language."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._language = Language(user_input[CONF_LANGUAGE])
            return await self.async_step_mealie()
        default = language_for(self.hass.config.language).value
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_LANGUAGE, default=default): _language_selector()}
            ),
        )

    async def async_step_mealie(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Offer the optional Mealie connection."""
        options = ["manual", "skip"]
        if discover_mealie_entries(self.hass):
            options.insert(0, "reuse")
        return self.async_show_menu(step_id="mealie", menu_options=options)

    async def async_step_reuse(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reuse the credentials of Home Assistant's Mealie integration."""
        entries = discover_mealie_entries(self.hass)
        if user_input is not None:
            return self._create(
                {"mode": MODE_INTEGRATION, "entry_id": user_input["entry_id"]}
            )
        return self.async_show_form(
            step_id="reuse",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "entry_id", default=entries[0].entry_id
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": e.entry_id, "label": e.title} for e in entries
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter the Mealie URL and API token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = MealieClient(
                async_get_clientsession(self.hass, verify_ssl=user_input["verify_ssl"]),
                user_input["url"],
                user_input["token"],
            )
            try:
                await client.validate()
            except MealieAuthError:
                errors["base"] = "invalid_auth"
            except MealieError:
                errors["base"] = "cannot_connect"
            else:
                return self._create({"mode": MODE_MANUAL, **user_input})
        defaults = user_input or {}
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("url", default=defaults.get("url", "")): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                    vol.Required("token"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Required(
                        "verify_ssl", default=defaults.get("verify_ssl", True)
                    ): BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_skip(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Skip Mealie: seasonal information only."""
        return self._create({"mode": MODE_NONE})

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Mealie rejected the token: choose the connection again."""
        return await self.async_step_mealie()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change the Mealie connection without losing the stored corrections."""
        return await self.async_step_mealie()

    def _create(self, mealie: dict[str, Any]) -> FlowResult:
        if self.source == config_entries.SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates={CONF_MEALIE: mealie}
            )
        if self.source == config_entries.SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data_updates={CONF_MEALIE: mealie}
            )
        return self.async_create_entry(
            title="Seasonal Groceries",
            data={CONF_LANGUAGE: self._language.value, CONF_MEALIE: mealie},
        )


class SeasonalGroceriesOptionsFlow(config_entries.OptionsFlowWithReload):
    """Options: grocery language and alias write-back."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LANGUAGE, default=current.get(CONF_LANGUAGE, "en")
                    ): _language_selector(),
                    vol.Required(
                        CONF_WRITE_BACK, default=current.get(CONF_WRITE_BACK, False)
                    ): BooleanSelector(),
                }
            ),
        )
