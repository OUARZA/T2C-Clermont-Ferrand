"""T2C Clermont-Ferrand integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import T2CClient, T2CError, T2CRoute
from .const import (
    CONF_DIRECTION_ID,
    CONF_LINE_COLOR,
    CONF_LINE_ID,
    CONF_LINE_NAME,
    CONF_LINE_TEXT_COLOR,
    CONF_STOP_ID,
    CONF_STOPS,
    DOMAIN,
    GLOBAL_ENTRY_ID,
)
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
    configured_stops = await _async_enrich_stop_colors(hass, entry, client)

    stop_runtimes: list[T2CStopRuntimeData] = []
    for stop_data in configured_stops:
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


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a configured stop when its Home Assistant device is deleted."""
    device_keys = {
        identifier
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    }
    configured_stops = _configured_stops(entry)
    updated_stops = [
        stop for stop in configured_stops if _stop_key(stop) not in device_keys
    ]

    if len(updated_stops) == len(configured_stops):
        return False

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_STOPS: updated_stops,
        },
    )
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
    return True


def _configured_stops(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Return configured stops, supporting legacy one-stop entries."""
    stops = entry.data.get(CONF_STOPS)
    if isinstance(stops, list):
        return [dict(stop) for stop in stops if isinstance(stop, dict)]
    return [dict(entry.data)]


async def _async_enrich_stop_colors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: T2CClient,
) -> list[dict[str, Any]]:
    """Ensure configured stops include static GTFS line colors."""
    configured_stops = _configured_stops(entry)
    if all(
        stop.get(CONF_LINE_COLOR) and stop.get(CONF_LINE_TEXT_COLOR)
        for stop in configured_stops
    ):
        return configured_stops

    try:
        routes = await client.async_get_routes()
    except T2CError:
        _LOGGER.debug("Unable to enrich T2C line colors from GTFS", exc_info=True)
        return configured_stops

    routes_by_key = _routes_by_key(routes)
    updated_stops: list[dict[str, Any]] = []
    changed = False

    for stop_data in configured_stops:
        updated_stop = dict(stop_data)
        route = routes_by_key.get(str(updated_stop.get(CONF_LINE_ID) or ""))
        route = route or routes_by_key.get(str(updated_stop.get(CONF_LINE_NAME) or ""))

        if route is not None:
            if route.short_name and not updated_stop.get(CONF_LINE_NAME):
                updated_stop[CONF_LINE_NAME] = route.short_name
                changed = True
            if route.color and not updated_stop.get(CONF_LINE_COLOR):
                updated_stop[CONF_LINE_COLOR] = route.color
                changed = True
            if route.text_color and not updated_stop.get(CONF_LINE_TEXT_COLOR):
                updated_stop[CONF_LINE_TEXT_COLOR] = route.text_color
                changed = True

        updated_stops.append(updated_stop)

    if changed:
        data = (
            {**entry.data, CONF_STOPS: updated_stops}
            if CONF_STOPS in entry.data
            else {**entry.data, **updated_stops[0]}
        )
        hass.config_entries.async_update_entry(entry, data=data)

    return updated_stops


def _routes_by_key(routes: list[T2CRoute]) -> dict[str, T2CRoute]:
    """Return routes indexed by internal ID and public short name."""
    routes_by_key: dict[str, T2CRoute] = {}
    for route in routes:
        routes_by_key[route.route_id] = route
        routes_by_key[route.short_name] = route
    return routes_by_key


def _stop_key(stop_data: dict[str, Any]) -> str:
    """Return a stable identifier for a configured stop."""
    return "_".join(
        str(stop_data.get(key, ""))
        for key in (CONF_LINE_ID, CONF_DIRECTION_ID, CONF_STOP_ID)
    )
