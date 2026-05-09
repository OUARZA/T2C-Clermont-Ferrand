"""Config flow for T2C Clermont-Ferrand."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_DIRECTION_ID,
    CONF_DIRECTION_NAME,
    CONF_LINE_ID,
    CONF_LINE_NAME,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
)


class T2CClermontFerrandConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for T2C Clermont-Ferrand."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LINE_ID]}_{user_input[CONF_DIRECTION_ID]}_{user_input[CONF_STOP_ID]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{user_input[CONF_LINE_NAME]} - {user_input[CONF_STOP_NAME]}",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_LINE_NAME): str,
                vol.Required(CONF_LINE_ID): str,
                vol.Required(CONF_DIRECTION_NAME): str,
                vol.Required(CONF_DIRECTION_ID): str,
                vol.Required(CONF_STOP_NAME): str,
                vol.Required(CONF_STOP_ID): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
