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
    ATTR_COUNT,
    ATTR_DEPARTURES,
    ATTR_DUE_AT,
    ATTR_DIRECTION,
    ATTR_DESTINATION,
    ATTR_ESTIMATED_AT,
    ATTR_LINE,
    ATTR_LABEL,
    ATTR_MESSAGES,
    ATTR_MINUTES,
    ATTR_INFO,
    ATTR_NEXT_PASSAGES,
    ATTR_RAW_PASSAGES,
    ATTR_REALTIME,
    ATTR_ROUTE_COLOR,
    ATTR_ROUTE_ID,
    ATTR_ROUTE_TEXT_COLOR,
    ATTR_SCHEDULED_AT,
    ATTR_STATUS,
    ATTR_STOP,
    ATTR_STOP_ID,
    ATTR_LEVEL,
    ATTR_PRIORITY,
    ATTR_TRIP_ID,
    ATTR_THEORETICAL,
    ATTR_UPDATED_AT,
    ATTR_VALID_FROM,
    ATTR_VALID_UNTIL,
    ATTR_VEHICLE_ID,
    CONF_DEPARTURE_LIMIT,
    CONF_DIRECTION_NAME,
    CONF_LINE_NAME,
    CONF_STOP_NAME,
    DEFAULT_DEPARTURE_LIMIT,
    DOMAIN,
    GLOBAL_ENTRY_ID,
)
from .coordinator import T2CDataUpdateCoordinator, T2CNetworkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up T2C sensors."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    network_coordinator = runtime_data.network_coordinator
    domain_data = hass.data[DOMAIN]
    add_global_entities = GLOBAL_ENTRY_ID not in domain_data

    if add_global_entities:
        domain_data[GLOBAL_ENTRY_ID] = entry.entry_id

    entities: list[SensorEntity] = []
    for stop_runtime in runtime_data.stops:
        stop_data = stop_runtime.data
        coordinator = stop_runtime.coordinator
        departure_limit = stop_data.get(
            CONF_DEPARTURE_LIMIT,
            DEFAULT_DEPARTURE_LIMIT,
        )
        departure_sensors = [
            T2CDepartureTimeSensor(coordinator, stop_data, stop_runtime.key, index)
            for index in range(departure_limit)
        ]
        entities.extend(
            [
                T2CNextPassageSensor(coordinator, stop_data, stop_runtime.key),
                T2CUpcomingPassagesSensor(coordinator, stop_data, stop_runtime.key),
                T2CLineAlertsSensor(coordinator, stop_data, stop_runtime.key),
                *departure_sensors,
            ]
        )

    if add_global_entities:
        entities.append(T2CNetworkInformationSensor(network_coordinator))

    async_add_entities(entities)


class T2CBaseSensor(CoordinatorEntity[T2CDataUpdateCoordinator], SensorEntity):
    """Base class for T2C sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        stop_data: dict[str, Any],
        device_key: str,
        key: str,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._stop_data = stop_data
        self._device_key = device_key
        self._attr_unique_id = f"{DOMAIN}_{device_key}_{key}"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_key)},
            "name": _format_device_name(self._stop_data),
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
        stop_data: dict[str, Any],
        device_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, stop_data, device_key, "next_passage")

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
            ATTR_LINE: first.get("route_name") or self._stop_data.get(CONF_LINE_NAME),
            ATTR_ROUTE_COLOR: first.get("route_color"),
            ATTR_ROUTE_TEXT_COLOR: first.get("route_text_color"),
            ATTR_DIRECTION: self._stop_data.get(CONF_DIRECTION_NAME),
            ATTR_STOP: self._stop_data[CONF_STOP_NAME],
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
        stop_data: dict[str, Any],
        device_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, stop_data, device_key, "upcoming_passages")

    @property
    def native_value(self) -> int:
        """Return available departure count."""
        return len(_departures(self.coordinator))

    @property
    def extra_state_attributes(self):
        """Return all upcoming departures."""
        data = _departures(self.coordinator)
        return {
            ATTR_LINE: (
                data[0].get("route_name")
                if data
                else self._stop_data.get(CONF_LINE_NAME)
            ),
            ATTR_ROUTE_COLOR: data[0].get("route_color") if data else None,
            ATTR_ROUTE_TEXT_COLOR: data[0].get("route_text_color") if data else None,
            ATTR_DIRECTION: self._stop_data.get(CONF_DIRECTION_NAME),
            ATTR_STOP: self._stop_data[CONF_STOP_NAME],
            ATTR_NEXT_PASSAGES: [item.get("label") for item in data],
            ATTR_DEPARTURES: _format_departure_table(data),
            ATTR_MESSAGES: _messages(self.coordinator),
            ATTR_ALERTS: _alerts(self.coordinator),
            ATTR_RAW_PASSAGES: data,
        }


class T2CNetworkInformationSensor(
    CoordinatorEntity[T2CNetworkCoordinator],
    SensorEntity,
):
    """Sensor exposing global T2C network information."""

    _attr_has_entity_name = True
    _attr_name = "Informations réseau"
    _attr_unique_id = f"{DOMAIN}_network_information"

    def __init__(self, coordinator: T2CNetworkCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, "network")},
            "name": "Informations réseau",
            "manufacturer": "T2C Clermont-Ferrand",
            "model": "Informations réseau",
        }

    @property
    def native_value(self) -> str | None:
        """Return the first network message."""
        messages = _network_messages(self.coordinator)
        if not messages:
            return None
        return _format_alert_summary(messages[0])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return network message details."""
        messages = _network_messages(self.coordinator)
        first = messages[0] if messages else {}

        return {
            ATTR_COUNT: len(messages),
            ATTR_MESSAGES: messages,
            "title": first.get("title"),
            "text": first.get("text"),
            "type": first.get("type"),
            ATTR_LEVEL: first.get("disruption_level"),
            ATTR_PRIORITY: first.get("priority"),
            ATTR_UPDATED_AT: first.get("updated_at"),
            ATTR_AFFECTED_ROUTES: first.get("affected_routes"),
        }


class T2CLineAlertsSensor(T2CBaseSensor):
    """Sensor exposing line disruptions from the T2C alerts API."""

    _attr_name = "Perturbations ligne"

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        stop_data: dict[str, Any],
        device_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, stop_data, device_key, "line_alerts")

    @property
    def native_value(self) -> str | None:
        """Return the first line alert title."""
        alerts = _alerts(self.coordinator)
        if not alerts:
            return "Aucune perturbation"
        return alerts[0].get("title") or "Perturbation"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return line alert details."""
        alerts = _alerts(self.coordinator)
        first = alerts[0] if alerts else {}

        return {
            ATTR_LINE: self._stop_data.get(CONF_LINE_NAME),
            ATTR_DIRECTION: self._stop_data.get(CONF_DIRECTION_NAME),
            ATTR_COUNT: len(alerts),
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
    """Sensor exposing one upcoming departure in T2C display format."""

    def __init__(
        self,
        coordinator: T2CDataUpdateCoordinator,
        stop_data: dict[str, Any],
        device_key: str,
        index: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            stop_data,
            device_key,
            f"departure_{index + 1}",
        )
        self._index = index
        self._attr_name = f"Passage {index + 1}"

    @property
    def native_value(self) -> str | None:
        """Return the departure display value."""
        departure = self._departure
        if departure is None:
            return "Fin de service"

        if departure.get("status") == "cancelled":
            time_value = _format_departure_time(
                departure,
                _parse_datetime(departure.get("due_at")),
            )
            return f"{time_value} annulé" if time_value else "Annulé"

        due_at = _parse_datetime(departure.get("due_at"))
        if self._index == 0:
            return _format_minutes(departure.get("minutes")) or "Aucune info"

        return _format_departure_time(departure, due_at) or "Aucune info"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return departure details."""
        departure = self._departure or {}
        return {
            ATTR_LINE: departure.get("route_name") or self._stop_data.get(CONF_LINE_NAME),
            ATTR_ROUTE_ID: departure.get("route_id"),
            ATTR_ROUTE_COLOR: departure.get("route_color"),
            ATTR_ROUTE_TEXT_COLOR: departure.get("route_text_color"),
            ATTR_DIRECTION: self._stop_data.get(CONF_DIRECTION_NAME),
            ATTR_STOP: self._stop_data[CONF_STOP_NAME],
            ATTR_STOP_ID: departure.get("stop_id"),
            ATTR_DESTINATION: departure.get("destination"),
            ATTR_LABEL: departure.get("label"),
            ATTR_DUE_AT: departure.get("due_at"),
            ATTR_SCHEDULED_AT: departure.get("scheduled_at"),
            ATTR_ESTIMATED_AT: departure.get("estimated_at"),
            ATTR_MINUTES: departure.get("minutes"),
            ATTR_INFO: _format_departure_info(departure) or "Aucune info",
            ATTR_STATUS: departure.get("status"),
            ATTR_THEORETICAL: departure.get("theoretical"),
            ATTR_REALTIME: departure.get("realtime"),
            ATTR_TRIP_ID: departure.get("trip_id"),
            ATTR_VEHICLE_ID: departure.get("vehicle_id"),
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
                "couleur_ligne": item.get("route_color"),
                "couleur_texte_ligne": item.get("route_text_color"),
                "destination": item.get("destination"),
                "depart": _format_departure_time(item, due_at),
                "info": _format_departure_info(item) or "Aucune info",
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
    info = item.get("info")
    if isinstance(info, str) and info.strip():
        return info.strip()
    return None


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


def _network_messages(
    coordinator: T2CNetworkCoordinator,
) -> list[dict[str, Any]]:
    """Return global network messages from coordinator data."""
    data = coordinator.data or {}
    return data.get("messages", [])


def _alerts(coordinator: T2CDataUpdateCoordinator) -> list[dict[str, Any]]:
    """Return line alerts from coordinator data."""
    data = coordinator.data or {}
    return data.get("alerts", [])


def _format_device_name(stop_data: dict[str, Any]) -> str:
    """Format the Home Assistant device name."""
    return (
        f"Ligne {stop_data[CONF_LINE_NAME]} - "
        f"Direction {stop_data[CONF_DIRECTION_NAME]} - "
        f"Arrêt {stop_data[CONF_STOP_NAME]}"
    )


def _format_alert_summary(
    alert: dict[str, Any],
    *,
    include_updated_at: bool = False,
) -> str | None:
    """Format a line alert state as title and message."""
    title = alert.get("title")
    text = alert.get("text")
    parts = [str(value) for value in (title, text) if value]

    if include_updated_at and (updated_at := _format_updated_at(alert)):
        parts.append(f"Mise à jour le {updated_at}")

    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} : {' - '.join(parts[1:])}"


def _format_updated_at(alert: dict[str, Any]) -> str | None:
    """Format an alert update timestamp for display."""
    updated_at = _parse_datetime(alert.get("updated_at"))
    if updated_at is None:
        return None
    return dt_util.as_local(updated_at).strftime("%d/%m/%Y %H:%M")
