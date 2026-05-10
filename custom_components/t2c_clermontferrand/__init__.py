"""T2C Clermont-Ferrand integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import T2CClient
from .const import CONF_STOPS, DOMAIN, GLOBAL_ENTRY_ID
from .coordinator import T2CDataUpdateCoordinator, T2CNetworkCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class T2CStopRuntimeData:
    """Runtime data stored for a configured T2C stop."""

    key: str
    data: dict[str, Any]
    coordinator: T2CDataUpdateCoordinator


@dataclass(slots=True)
class T2CRuntimeData:
    """Runtime data stored for a T2C config entry."""

    client: T2CClient
    stops: list[T2CStopRuntimeData]
    network_coordinator: T2CNetworkCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up T2C Clermont-Ferrand from a config entry."""
    client = T2CClient(async_get_clientsession(hass))
    network_coordinator = T2CNetworkCoordinator(hass, client)

    stop_runtimes: list[T2CStopRuntimeData] = []
    for stop_data in _configured_stops(entry):
        key = _stop_key(stop_data)
        coordinator = T2CDataUpdateCoordinator(
            hass,
            entry,
            client,
            stop_data=stop_data,
            name_suffix=key,
        )
        await coordinator.async_config_entry_first_refresh()
        stop_runtimes.append(
            T2CStopRuntimeData(
                key=key,
                data=stop_data,
                coordinator=coordinator,
            )
        )

    await network_coordinator.async_refresh()
    if not network_coordinator.last_update_success:
        _LOGGER.debug("T2C network information is unavailable during setup")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = T2CRuntimeData(
        client=client,
        stops=stop_runtimes,
        network_coordinator=network_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        domain_data = hass.data[DOMAIN]

        if domain_data.get(GLOBAL_ENTRY_ID) == entry.entry_id:
            domain_data.pop(GLOBAL_ENTRY_ID, None)

        domain_data.pop(entry.entry_id, None)
        if not any(
            isinstance(value, T2CRuntimeData) for value in domain_data.values()
        ):
            hass.data.pop(DOMAIN)

    return unload_ok


def _configured_stops(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Return configured stops, supporting legacy one-stop entries."""
    stops = entry.data.get(CONF_STOPS)
    if isinstance(stops, list):
        return [dict(stop) for stop in stops if isinstance(stop, dict)]
    return [dict(entry.data)]


def _stop_key(stop_data: dict[str, Any]) -> str:
    """Return a stable identifier for a configured stop."""
    return "_".join(
        str(stop_data.get(key, ""))
        for key in ("line_id", "direction_id", "stop_id")
    )
