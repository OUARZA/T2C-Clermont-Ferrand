"""DataUpdateCoordinator for T2C Clermont-Ferrand."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import T2CClient, T2CError
from .const import (
    CONF_DEPARTURE_LIMIT,
    CONF_LINE_ID,
    CONF_MONITORING_MODE,
    CONF_STOP_ID,
    DEFAULT_DEPARTURE_LIMIT,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MODE_LINE,
)

_LOGGER = logging.getLogger(__name__)


class T2CDataUpdateCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Coordinate polling of T2C GTFS-Realtime departures."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: T2CClient,
        stop_data: dict[str, Any] | None = None,
        name_suffix: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name_suffix or entry.entry_id}",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.client = client
        self.stop_data = stop_data or dict(entry.data)

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch latest departure data."""
        departure_limit = self.entry.data.get(
            CONF_DEPARTURE_LIMIT,
            DEFAULT_DEPARTURE_LIMIT,
        )
        departure_limit = self.stop_data.get(CONF_DEPARTURE_LIMIT, departure_limit)
        try:
            departures = await self.client.async_get_timetable_departures(
                stop_id=self.stop_data[CONF_STOP_ID],
                limit=departure_limit,
                route_id=self.stop_data.get(CONF_LINE_ID),
            )
        except T2CError as err:
            _LOGGER.debug("T2C coordinator update failed", exc_info=True)
            raise UpdateFailed(str(err)) from err

        try:
            messages = await self.client.async_get_stop_messages(
                stop_id=self.stop_data[CONF_STOP_ID],
                limit=departure_limit,
            )
        except T2CError:
            _LOGGER.debug("T2C information messages update failed", exc_info=True)
            messages = []

        alerts = []
        if self.stop_data.get(CONF_MONITORING_MODE, MODE_LINE) == MODE_LINE:
            try:
                alerts = await self.client.async_get_line_alerts(
                    self.stop_data[CONF_LINE_ID],
                )
            except T2CError:
                _LOGGER.debug("T2C line alerts update failed", exc_info=True)
                alerts = []

        _LOGGER.debug(
            "Coordinator fetched %s departures, %s messages and %s alerts for stop %s",
            len(departures),
            len(messages),
            len(alerts),
            self.stop_data[CONF_STOP_ID],
        )
        return {
            "departures": departures,
            "messages": messages,
            "alerts": alerts,
        }


class T2CNetworkCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Coordinate polling of global T2C network information."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: T2CClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_network",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch latest network information."""
        try:
            messages = await self.client.async_get_network_messages()
        except T2CError as err:
            _LOGGER.debug("T2C network messages update failed", exc_info=True)
            raise UpdateFailed(str(err)) from err

        _LOGGER.debug("Network coordinator fetched %s messages", len(messages))
        return {"messages": messages}
