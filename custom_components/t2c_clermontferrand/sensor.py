"""Sensors for T2C Clermont-Ferrand."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AFFECTED_ROUTES,
    ATTR_ALERTS,
    ATTR_DEPARTURES,
    ATTR_DUE_AT,
    ATTR_DIRECTION,
    ATTR_DESTINATION,
    ATTR_ESTIMATED_AT,
    ATTR_LINE,
    ATTR_MESSAGES,
    ATTR_MINUTES,
    ATTR_NEXT_PASSAGES,
    ATTR_RAW_PASSAGES,
    ATTR_REALTIME,
    ATTR_SCHEDULED_AT,
    ATTR_SCOPE,
    ATTR_STATUS,
    ATTR_STOP,
    ATTR_LINE_REFS,
    ATTR_STOP_REFS,
    ATTR_LEVEL,
    ATTR_PRIORITY,
    ATTR_TRIP_ID,
    ATTR_THEORETICAL,
    ATTR_UPDATED_AT,
    ATTR_VALID_FROM,
    ATTR_VALID_UNTIL,
    CONF_DEPARTURE_LIMIT,
    CONF_DIRECTION_NAME,
    CONF_LINE_NAME,
    CONF_STOP_NAME,
    DEFAULT_DEPARTURE_LIMIT,
    DOMAIN,
)
from .coordinator import T2CDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up T2C sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    departure_limit = entry.data.get(CONF_DEPARTURE_LIMIT, DEFAULT_DEPARTURE_LIMIT)
    departure_sensors = [
        T2CDepartureTimeSensor(coordinator, entry, index)
        for index in range(departure_limit)
    ]
    async_add_entities(
        [
            T2CNextPassageSensor(coordinator, entry),
            T2CUpcomingPassagesSensor(coordinator, entry),
            T2CInformationMessagesSensor(coordinator, entry),
            T2CLineAlertsSensor(coordinator, entry),
            *departure_sensors,
        ]
    )


class T2CBaseSensor(CoordinatorEntity[T2CDataUpdateCoordinator], SensorEntity):
    """Base class for T2C sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": _format_device_name(self._entry),
            "manufacturer": "T2C Clermont-Ferrand",
            "model": "GTFS-Realtime Trip Updates",
        }


class T2CNextPassageSensor(T2CBaseSensor):
    """Sensor showing the next T2C passage."""

    _attr_name = "Prochain passage"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "next_passage")

    @property
    def native_value(self):
        """Return next passage in minutes."""
        data = _active_departures(self.coordinator)
        if not data:
            return None

        first = data[0]
        return first.get("minutes")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        data = _departures(self.coordinator)
        active_data = _active_departures(self.coordinator)
        first = active_data[0] if active_data else {}

        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_DESTINATION: first.get("destination"),
            ATTR_DUE_AT: first.get("due_at"),
            ATTR_STATUS: first.get("status"),
            ATTR_THEORETICAL: first.get("theoretical"),
            ATTR_REALTIME: first.get("realtime"),
            ATTR_NEXT_PASSAGES: [item.get("label") for item in data],
            ATTR_DEPARTURES: _format_departure_table(data),
            ATTR_MESSAGES: _messages(self.coordinator),
            ATTR_ALERTS: _alerts(self.coordinator),
            ATTR_RAW_PASSAGES: data,
        }


class T2CUpcomingPassagesSensor(T2CBaseSensor):
    """Sensor showing how many upcoming departures are available."""

    _attr_name = "Passages disponibles"

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "upcoming_passages")

    @property
    def native_value(self) -> int:
        """Return available departure count."""
        return len(_departures(self.coordinator))

    @property
    def extra_state_attributes(self):
        """Return all upcoming departures."""
        data = _departures(self.coordinator)
        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_NEXT_PASSAGES: [item.get("label") for item in data],
            ATTR_DEPARTURES: _format_departure_table(data),
            ATTR_MESSAGES: _messages(self.coordinator),
            ATTR_ALERTS: _alerts(self.coordinator),
            ATTR_RAW_PASSAGES: data,
        }


class T2CInformationMessagesSensor(T2CBaseSensor):
    """Sensor exposing information messages from T2C timetable API."""

    _attr_name = "Messages d'information"

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "information_messages")

    @property
    def native_value(self) -> int:
        """Return available information message count."""
        return len(_messages(self.coordinator))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return information message details."""
        messages = _messages(self.coordinator)
        first = messages[0] if messages else {}

        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_MESSAGES: messages,
            "title": first.get("title"),
            "content": first.get("content"),
            ATTR_SCOPE: first.get("scope"),
            ATTR_VALID_FROM: first.get("valid_from"),
            ATTR_VALID_UNTIL: first.get("valid_until"),
            ATTR_LINE_REFS: first.get("line_refs"),
            ATTR_STOP_REFS: first.get("stop_refs"),
        }


class T2CLineAlertsSensor(T2CBaseSensor):
    """Sensor exposing line disruptions from the T2C alerts API."""

    _attr_name = "Perturbations ligne"

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "line_alerts")

    @property
    def native_value(self) -> int:
        """Return available line alert count."""
        return len(_alerts(self.coordinator))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return line alert details."""
        alerts = _alerts(self.coordinator)
        first = alerts[0] if alerts else {}

        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_ALERTS: alerts,
            "title": first.get("title"),
            "text": first.get("text"),
            "type": first.get("type"),
            ATTR_LEVEL: first.get("disruption_level"),
            ATTR_PRIORITY: first.get("priority"),
            ATTR_UPDATED_AT: first.get("updated_at"),
            ATTR_AFFECTED_ROUTES: first.get("affected_routes"),
        }


class T2CDepartureTimeSensor(T2CBaseSensor):
    """Sensor exposing one upcoming departure as a timestamp."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        entry: ConfigEntry,
        index: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, f"departure_{index + 1}")
        self._index = index
        self._attr_name = f"Passage {index + 1}"

    @property
    def native_value(self) -> datetime | None:
        """Return the departure time."""
        departure = self._departure
        if departure is None:
            return None

        return _parse_datetime(departure.get("due_at"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return departure details."""
        departure = self._departure or {}
        return {
            ATTR_LINE: departure.get("route_name") or self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_DESTINATION: departure.get("destination"),
            ATTR_DUE_AT: departure.get("due_at"),
            ATTR_SCHEDULED_AT: departure.get("scheduled_at"),
            ATTR_ESTIMATED_AT: departure.get("estimated_at"),
            ATTR_MINUTES: departure.get("minutes"),
            ATTR_STATUS: departure.get("status"),
            ATTR_THEORETICAL: departure.get("theoretical"),
            ATTR_REALTIME: departure.get("realtime"),
            ATTR_TRIP_ID: departure.get("trip_id"),
        }

    @property
    def _departure(self) -> dict[str, Any] | None:
        """Return the departure represented by this sensor."""
        data = _departures(self.coordinator)
        if self._index >= len(data):
            return None
        return data[self._index]


def _format_departure_table(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return table-friendly departure attributes."""
    departures: list[dict[str, Any]] = []

    for item in data:
        due_at = _parse_datetime(item.get("due_at"))
        departures.append(
            {
                "ligne": item.get("route_name"),
                "destination": item.get("destination"),
                "depart": _format_departure_time(item, due_at),
                "info": _format_departure_info(item),
                "etat": item.get("status"),
                "theorique": item.get("theoretical"),
                "temps_reel": item.get("realtime"),
            }
        )

    return departures


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a Home Assistant compatible datetime value."""
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


def _format_minutes(value: Any) -> str | None:
    """Format a departure delay for display attributes."""
    if not isinstance(value, int):
        return None
    if value == 0:
        return "A l'approche"
    return f"{value} min"


def _format_departure_time(item: dict[str, Any], due_at: datetime | None) -> str | None:
    """Format the departure time like the T2C timetable."""
    if due_at is None:
        return None

    prefix = "*" if item.get("theoretical") else ""
    return f"{prefix}{dt_util.as_local(due_at).strftime('%H:%M')}"


def _format_departure_info(item: dict[str, Any]) -> str | None:
    """Format timetable status information."""
    if item.get("status") == "cancelled":
        return "Annulé"
    return _format_minutes(item.get("minutes"))


def _departures(coordinator: T2CDataUpdateCoordinator) -> list[dict[str, Any]]:
    """Return departures from coordinator data."""
    data = coordinator.data or {}
    return data.get("departures", [])


def _active_departures(
    coordinator: T2CDataUpdateCoordinator,
) -> list[dict[str, Any]]:
    """Return departures that are not cancelled."""
    return [
        departure
        for departure in _departures(coordinator)
        if departure.get("status") != "cancelled"
    ]


def _messages(coordinator: T2CDataUpdateCoordinator) -> list[dict[str, Any]]:
    """Return information messages from coordinator data."""
    data = coordinator.data or {}
    return data.get("messages", [])


def _alerts(coordinator: T2CDataUpdateCoordinator) -> list[dict[str, Any]]:
    """Return line alerts from coordinator data."""
    data = coordinator.data or {}
    return data.get("alerts", [])


def _format_device_name(entry: ConfigEntry) -> str:
    """Format the Home Assistant device name."""
    return (
        f"T2C - Ligne {entry.data[CONF_LINE_NAME]} - "
        f"Direction {entry.data[CONF_DIRECTION_NAME]} - "
        f"Arrêt {entry.data[CONF_STOP_NAME]}"
    )
