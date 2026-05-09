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
    CONF_DIRECTION_ID,
    CONF_LINE_ID,
    CONF_STOP_ID,
    DEFAULT_DEPARTURE_LIMIT,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class T2CDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinate polling of T2C GTFS-Realtime departures."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: T2CClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch latest departure data."""
        try:
            data = await self.client.async_get_next_departures(
                stop_id=self.entry.data[CONF_STOP_ID],
                route_id=self.entry.data.get(CONF_LINE_ID),
                direction_id=self.entry.data.get(CONF_DIRECTION_ID),
                limit=DEFAULT_DEPARTURE_LIMIT,
            )
        except T2CError as err:
            _LOGGER.debug("T2C coordinator update failed", exc_info=True)
            raise UpdateFailed(str(err)) from err

        _LOGGER.debug(
            "Coordinator fetched %s departures for stop %s",
            len(data),
            self.entry.data[CONF_STOP_ID],
        )
        return data
