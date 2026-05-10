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

from .api import T2CClient, T2CDirection, T2CError, T2CRoute, T2CStop
from .const import (
    CONF_DEPARTURE_LIMIT,
    CONF_DIRECTION_ID,
    CONF_DIRECTION_NAME,
    CONF_LINE_ID,
    CONF_LINE_NAME,
    CONF_MONITORING_MODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_STOPS,
    DEFAULT_DEPARTURE_LIMIT,
    DOMAIN,
    MAX_DEPARTURE_LIMIT,
    MIN_DEPARTURE_LIMIT,
    MODE_LINE,
    MODE_STOP,
)

_LOGGER = logging.getLogger(__name__)


class T2CClermontFerrandConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for T2C Clermont-Ferrand."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._routes: dict[str, T2CRoute] = {}
        self._directions: dict[str, T2CDirection] = {}
        self._stops: dict[str, T2CStop] = {}
        self._monitoring_mode: str | None = None
        self._route_id: str | None = None
        self._direction_id: str | None = None
        self._stop_id: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select the monitoring mode."""

        if user_input is not None:
            self._monitoring_mode = user_input[CONF_MONITORING_MODE]
            if self._monitoring_mode == MODE_STOP:
                return await self.async_step_stop_all()
            return await self.async_step_line()

        schema = vol.Schema(
            {
                vol.Required(CONF_MONITORING_MODE): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=MODE_STOP,
                                label="Tous les passages à un arrêt",
                            ),
                            SelectOptionDict(
                                value=MODE_LINE,
                                label="Une ligne, une direction et un arrêt",
                            ),
                        ],
                    )
                )
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_line(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select the T2C line."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._route_id = user_input[CONF_LINE_ID]
            return await self.async_step_direction()

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
            step_id="line",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_stop_all(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a stop without filtering by line."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._stop_id = user_input[CONF_STOP_ID]
            return await self.async_step_departures()

        try:
            stops = await self._async_get_all_stops()
        except T2CError:
            _LOGGER.exception("Unable to load T2C stops")
            errors["base"] = "cannot_connect"
            stops = []

        self._stops = {stop.stop_id: stop for stop in stops}
        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=stop.stop_id,
                                label=f"{stop.name} ({stop.stop_id})",
                            )
                            for stop in stops
                        ],
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="stop_all",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_direction(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select the T2C direction."""
        errors: dict[str, str] = {}

        if self._route_id is None:
            return await self.async_step_line()

        route = self._routes.get(self._route_id)
        if route is None:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self._direction_id = user_input[CONF_DIRECTION_ID]
            return await self.async_step_stop()

        try:
            directions = await self._async_get_directions(self._route_id)
        except T2CError:
            _LOGGER.exception(
                "Unable to load T2C directions for route %s",
                self._route_id,
            )
            errors["base"] = "cannot_connect"
            directions = []

        self._directions = {
            direction.direction_id: direction for direction in directions
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_DIRECTION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=direction.direction_id,
                                label=direction.name,
                            )
                            for direction in directions
                        ],
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="direction",
            data_schema=schema,
            errors=errors,
            description_placeholders={"line": route.label},
        )

    async def async_step_stop(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select the T2C stop."""
        errors: dict[str, str] = {}

        if self._route_id is None:
            return await self.async_step_line()
        if self._direction_id is None:
            return await self.async_step_direction()

        route = self._routes.get(self._route_id)
        direction = self._directions.get(self._direction_id)
        if route is None:
            return self.async_abort(reason="cannot_connect")
        if direction is None:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self._stop_id = user_input[CONF_STOP_ID]
            return await self.async_step_departures()

        try:
            stops = await self._async_get_stops(self._route_id, self._direction_id)
        except T2CError:
            _LOGGER.exception(
                "Unable to load T2C stops for route %s direction %s",
                self._route_id,
                self._direction_id,
            )
            errors["base"] = "cannot_connect"
            stops = []

        self._stops = {stop.stop_id: stop for stop in stops}
        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=stop.stop_id, label=stop.name)
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
            description_placeholders={
                "direction": direction.name,
                "line": route.label,
            },
        )

    async def async_step_departures(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select how many upcoming departures should be exposed."""
        if self._monitoring_mode == MODE_STOP:
            if self._stop_id is None:
                return await self.async_step_stop_all()
        else:
            if self._route_id is None:
                return await self.async_step_line()
            if self._direction_id is None:
                return await self.async_step_direction()
            if self._stop_id is None:
                return await self.async_step_stop()

        route = self._routes.get(self._route_id or "")
        direction = self._directions.get(self._direction_id or "")
        stop = self._stops.get(self._stop_id)

        if self._monitoring_mode == MODE_LINE and (
            route is None or direction is None or stop is None
        ):
            return self.async_abort(reason="cannot_connect")
        if self._monitoring_mode == MODE_STOP and stop is None:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            departure_limit = user_input[CONF_DEPARTURE_LIMIT]
            stop_config: dict[str, Any] = {
                CONF_MONITORING_MODE: self._monitoring_mode or MODE_LINE,
                CONF_STOP_ID: stop.stop_id,
                CONF_STOP_NAME: stop.name,
                CONF_DEPARTURE_LIMIT: departure_limit,
            }
            if self._monitoring_mode == MODE_LINE:
                stop_config.update(
                    {
                        CONF_LINE_ID: route.route_id,
                        CONF_LINE_NAME: route.short_name,
                        CONF_DIRECTION_ID: direction.direction_id,
                        CONF_DIRECTION_NAME: direction.name,
                    }
                )
            stop_key = _stop_key(stop_config)
            existing_entry = self._find_existing_hub_entry()

            if existing_entry is not None:
                configured_stops = _configured_stops(existing_entry.data)
                already_configured = any(
                    _stop_key(configured) == stop_key
                    for configured in configured_stops
                )
                if already_configured:
                    return self.async_abort(reason="already_configured")

                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_STOPS: [*configured_stops, stop_config],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing_entry.entry_id)
                )
                return self.async_abort(reason="stop_added")

            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=_format_entry_title(),
                data={CONF_STOPS: [stop_config]},
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEPARTURE_LIMIT,
                    default=DEFAULT_DEPARTURE_LIMIT,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_DEPARTURE_LIMIT, max=MAX_DEPARTURE_LIMIT),
                )
            }
        )

        return self.async_show_form(
            step_id="departures",
            data_schema=schema,
            description_placeholders=_departure_placeholders(
                self._monitoring_mode or MODE_LINE,
                stop,
                route,
                direction,
            ),
        )

    async def _async_get_routes(self) -> list[T2CRoute]:
        """Load route options."""
        client = T2CClient(async_get_clientsession(self.hass))
        routes = await client.async_get_routes()
        self._routes = {route.route_id: route for route in routes}
        return routes

    async def _async_get_all_stops(self) -> list[T2CStop]:
        """Load all stop options."""
        client = T2CClient(async_get_clientsession(self.hass))
        return await client.async_get_stops()

    async def _async_get_directions(self, route_id: str) -> list[T2CDirection]:
        """Load direction options."""
        client = T2CClient(async_get_clientsession(self.hass))
        return await client.async_get_directions_for_route(route_id)

    async def _async_get_stops(
        self,
        route_id: str,
        direction_id: str,
    ) -> list[T2CStop]:
        """Load stop options."""
        client = T2CClient(async_get_clientsession(self.hass))
        return await client.async_get_stops_for_direction(route_id, direction_id)

    def _find_existing_hub_entry(self) -> config_entries.ConfigEntry | None:
        """Return the existing hub config entry if it exists."""
        for entry in self._async_current_entries():
            if entry.unique_id == DOMAIN or CONF_STOPS in entry.data:
                return entry
        return None


def _format_entry_title() -> str:
    """Format the Home Assistant config entry title."""
    return "T2C - Clermont-Ferrand"


def _configured_stops(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return configured stops from a config entry data dict."""
    stops = data.get(CONF_STOPS)
    if isinstance(stops, list):
        return [dict(stop) for stop in stops if isinstance(stop, dict)]
    return [dict(data)]


def _stop_key(stop_data: dict[str, Any]) -> str:
    """Return a stable key for a selected monitoring target."""
    mode = stop_data.get(CONF_MONITORING_MODE, MODE_LINE)
    if mode == MODE_LINE:
        return "_".join(
            str(stop_data.get(key, ""))
            for key in (CONF_LINE_ID, CONF_DIRECTION_ID, CONF_STOP_ID)
        )

    return "_".join(
        str(value)
        for value in (
            mode,
            stop_data.get(CONF_STOP_ID, ""),
        )
    )


def _departure_placeholders(
    mode: str,
    stop: T2CStop,
    route: T2CRoute | None,
    direction: T2CDirection | None,
) -> dict[str, str]:
    """Return description placeholders for the departures step."""
    if mode == MODE_STOP:
        return {
            "target": f"l'arrêt {stop.name}",
            "direction": "toutes directions",
            "line": "toutes lignes",
            "stop": stop.name,
        }

    return {
        "target": (
            f"{stop.name}, ligne {route.label if route else ''}, "
            f"direction {direction.name if direction else ''}"
        ),
        "direction": direction.name if direction else "",
        "line": route.label if route else "",
        "stop": stop.name,
    }
