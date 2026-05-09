"""Sensors for T2C Clermont-Ferrand."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DUE_AT,
    ATTR_DIRECTION,
    ATTR_DESTINATION,
    ATTR_LINE,
    ATTR_NEXT_PASSAGES,
    ATTR_RAW_PASSAGES,
    ATTR_REALTIME,
    ATTR_STOP,
    CONF_DIRECTION_NAME,
    CONF_LINE_NAME,
    CONF_STOP_NAME,
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
    async_add_entities(
        [
            T2CNextPassageSensor(coordinator, entry),
            T2CUpcomingPassagesSensor(coordinator, entry),
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
            ATTR_RAW_PASSAGES: data,
        }
