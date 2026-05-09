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
    ATTR_DEPARTURES,
    ATTR_DUE_AT,
    ATTR_DIRECTION,
    ATTR_DESTINATION,
    ATTR_LINE,
    ATTR_MINUTES,
    ATTR_NEXT_PASSAGES,
    ATTR_RAW_PASSAGES,
    ATTR_REALTIME,
    ATTR_STOP,
    ATTR_TRIP_ID,
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
    departure_sensors = [
        T2CDepartureTimeSensor(coordinator, entry, index)
        for index in range(DEFAULT_DEPARTURE_LIMIT)
    ]
    async_add_entities(
        [
            T2CNextPassageSensor(coordinator, entry),
            T2CUpcomingPassagesSensor(coordinator, entry),
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
            "name": (
                f"T2C {self._entry.data[CONF_LINE_NAME]} - "
                f"{self._entry.data[CONF_STOP_NAME]}"
            ),
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
        data = self.coordinator.data or []
        if not data:
            return None

        first = data[0]
        return first.get("minutes")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        data = self.coordinator.data or []
        first = data[0] if data else {}

        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_DESTINATION: first.get("destination"),
            ATTR_DUE_AT: first.get("due_at"),
            ATTR_REALTIME: first.get("realtime"),
            ATTR_NEXT_PASSAGES: [item.get("label") for item in data],
            ATTR_DEPARTURES: _format_departure_table(data),
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
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self):
        """Return all upcoming departures."""
        data = self.coordinator.data or []
        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_NEXT_PASSAGES: [item.get("label") for item in data],
            ATTR_DEPARTURES: _format_departure_table(data),
            ATTR_RAW_PASSAGES: data,
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
            ATTR_MINUTES: departure.get("minutes"),
            ATTR_REALTIME: departure.get("realtime"),
            ATTR_TRIP_ID: departure.get("trip_id"),
        }

    @property
    def _departure(self) -> dict[str, Any] | None:
        """Return the departure represented by this sensor."""
        data = self.coordinator.data or []
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
                "depart": dt_util.as_local(due_at).strftime("%H:%M")
                if due_at
                else None,
                "info": _format_minutes(item.get("minutes")),
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
