"""Sensors for T2C Clermont-Ferrand."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DIRECTION,
    ATTR_LINE,
    ATTR_NEXT_PASSAGES,
    ATTR_RAW_PASSAGES,
    ATTR_STOP,
    CONF_DIRECTION_NAME,
    CONF_LINE_NAME,
    CONF_STOP_NAME,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up T2C sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([T2CNextPassageSensor(coordinator, entry)])


class T2CNextPassageSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the next T2C passage."""

    _attr_has_entity_name = True
    _attr_name = "Prochain passage"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_next_passage"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"T2C {self._entry.data[CONF_LINE_NAME]} - {self._entry.data[CONF_STOP_NAME]}",
            "manufacturer": "T2C Clermont-Ferrand",
        }

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

        return {
            ATTR_LINE: self._entry.data[CONF_LINE_NAME],
            ATTR_DIRECTION: self._entry.data[CONF_DIRECTION_NAME],
            ATTR_STOP: self._entry.data[CONF_STOP_NAME],
            ATTR_NEXT_PASSAGES: [item.get("label") for item in data],
            ATTR_RAW_PASSAGES: data,
        }
