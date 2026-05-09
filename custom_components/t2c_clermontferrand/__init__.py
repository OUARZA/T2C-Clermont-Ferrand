"""T2C Clermont-Ferrand integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import T2CClient
from .const import DOMAIN
from .coordinator import T2CDataUpdateCoordinator, T2CNetworkCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass(slots=True)
class T2CRuntimeData:
    """Runtime data stored for a T2C config entry."""

    client: T2CClient
    coordinator: T2CDataUpdateCoordinator
    network_coordinator: T2CNetworkCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up T2C Clermont-Ferrand from a config entry."""
    client = T2CClient(async_get_clientsession(hass))
    coordinator = T2CDataUpdateCoordinator(hass, entry, client)
    network_coordinator = T2CNetworkCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    await network_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = T2CRuntimeData(
        client=client,
        coordinator=coordinator,
        network_coordinator=network_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
