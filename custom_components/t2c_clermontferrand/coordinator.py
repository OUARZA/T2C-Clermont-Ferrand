"""DataUpdateCoordinator for T2C Clermont-Ferrand."""

from __future__ import annotations

from datetime import timedelta
import logging
import unicodedata
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import T2CClient, T2CError
from .const import (
    CONF_DEPARTURE_LIMIT,
    CONF_LINE_ID,
    CONF_STOP_ID,
    DEFAULT_DEPARTURE_LIMIT,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
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

        line_alerts_by_route: dict[str, list[dict[str, Any]]] = {}
        configured_line_id = self.stop_data[CONF_LINE_ID]
        try:
            alerts = await self.client.async_get_line_alerts(configured_line_id)
            line_alerts_by_route[configured_line_id] = alerts
        except T2CError:
            _LOGGER.debug("T2C line alerts update failed", exc_info=True)
            alerts = []

        for route_id in _departure_route_ids(departures):
            if route_id in line_alerts_by_route:
                continue
            try:
                line_alerts_by_route[route_id] = await self.client.async_get_line_alerts(
                    route_id,
                )
            except T2CError:
                _LOGGER.debug(
                    "T2C line alerts update failed for route %s",
                    route_id,
                    exc_info=True,
                )
                line_alerts_by_route[route_id] = []

        departures = _attach_line_alerts_to_departures(
            departures,
            line_alerts_by_route,
        )

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


def _departure_route_ids(departures: list[dict[str, Any]]) -> set[str]:
    """Return route IDs found in departures."""
    return {
        str(route_id)
        for departure in departures
        if (route_id := departure.get("route_id"))
    }


def _attach_line_alerts_to_departures(
    departures: list[dict[str, Any]],
    line_alerts_by_route: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Attach line alerts to each departure using the departure route."""
    enriched: list[dict[str, Any]] = []

    for departure in departures:
        item = dict(departure)
        route_id = str(item.get("route_id") or "")
        line_alerts = [
            alert
            for alert in line_alerts_by_route.get(route_id, [])
            if _alert_matches_departure(alert, item)
        ]
        first_alert = line_alerts[0] if line_alerts else {}

        item["line_alerts"] = line_alerts
        item["has_alert"] = bool(line_alerts)
        item["alert_icon"] = "mdi:alert-circle" if line_alerts else None
        item["alert_title"] = first_alert.get("title")
        item["alert_text"] = first_alert.get("text")
        item["alert_updated_at"] = first_alert.get("updated_at")
        if not item.get("info") and first_alert.get("title"):
            item["info"] = first_alert["title"]

        enriched.append(item)

    return enriched


def _alert_matches_departure(
    alert: dict[str, Any],
    departure: dict[str, Any],
) -> bool:
    """Return whether a line alert appears to apply to a departure."""
    text = _normalize_text(
        " ".join(
            str(value)
            for value in (alert.get("title"), alert.get("text"))
            if value
        )
    )
    destination = _normalize_text(str(departure.get("destination") or ""))

    if not text:
        return False
    if "dans les 2 sens" in text or "dans les deux sens" in text:
        return True
    if "direction" not in text:
        return True

    return bool(destination and destination in text)


def _normalize_text(value: str) -> str:
    """Return text normalized for loose matching."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        char for char in normalized.casefold() if not unicodedata.combining(char)
    )
