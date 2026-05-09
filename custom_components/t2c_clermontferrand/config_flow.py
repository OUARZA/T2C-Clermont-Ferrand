"""Config flow for T2C Clermont-Ferrand."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
import voluptuous as vol

from .api import T2CClient, T2CError, T2CRoute, T2CStop
from .const import (
    CONF_DIRECTION_ID,
    CONF_DIRECTION_NAME,
    CONF_LINE_ID,
    CONF_LINE_NAME,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class T2CClermontFerrandConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for T2C Clermont-Ferrand."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._routes: dict[str, T2CRoute] = {}
        self._stops: dict[str, T2CStop] = {}
        self._route_id: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select the T2C line."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._route_id = user_input[CONF_LINE_ID]
            return await self.async_step_stop()

        try:
            routes = await self._async_get_routes()
        except T2CError:
            _LOGGER.exception("Unable to load T2C routes")
            errors["base"] = "cannot_connect"
            routes = []

        schema = vol.Schema(
            {
                vol.Required(CONF_LINE_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=route.route_id, label=route.label)
                            for route in routes
                        ],
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_stop(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select the T2C stop."""
        errors: dict[str, str] = {}

        if self._route_id is None:
            return await self.async_step_user()

        route = self._routes.get(self._route_id)
        if route is None:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            stop = self._stops[user_input[CONF_STOP_ID]]
            unique_id = f"{self._route_id}_{stop.stop_id}_{stop.direction_id or 'all'}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{route.short_name} - {stop.label}",
                data={
                    CONF_LINE_ID: route.route_id,
                    CONF_LINE_NAME: route.short_name,
                    CONF_DIRECTION_ID: stop.direction_id,
                    CONF_DIRECTION_NAME: stop.direction_name,
                    CONF_STOP_ID: stop.stop_id,
                    CONF_STOP_NAME: stop.name,
                },
            )

        try:
            stops = await self._async_get_stops(self._route_id)
        except T2CError:
            _LOGGER.exception("Unable to load T2C stops for route %s", self._route_id)
            errors["base"] = "cannot_connect"
            stops = []

        self._stops = {stop.option_value: stop for stop in stops}
        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=stop.option_value, label=stop.label)
                            for stop in stops
                        ],
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="stop",
            data_schema=schema,
            errors=errors,
            description_placeholders={"line": route.label},
        )

    async def _async_get_routes(self) -> list[T2CRoute]:
        """Load route options."""
        client = T2CClient(async_get_clientsession(self.hass))
        routes = await client.async_get_routes()
        self._routes = {route.route_id: route for route in routes}
        return routes

    async def _async_get_stops(self, route_id: str) -> list[T2CStop]:
        """Load stop options."""
        client = T2CClient(async_get_clientsession(self.hass))
        return await client.async_get_stops_for_route(route_id)
