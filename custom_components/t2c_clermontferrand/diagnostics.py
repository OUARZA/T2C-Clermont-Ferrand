"""Diagnostics support for T2C Clermont-Ferrand."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    stop_runtimes = getattr(domain_data, "stops", [])
    network_coordinator = getattr(domain_data, "network_coordinator", None)
    client = getattr(domain_data, "client", None)
    gtfs = getattr(client, "_gtfs", None)

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": dict(entry.data),
        },
        "stops": [
            {
                "key": getattr(stop_runtime, "key", None),
                "data": getattr(stop_runtime, "data", None),
                "coordinator": {
                    "last_update_success": getattr(
                        getattr(stop_runtime, "coordinator", None),
                        "last_update_success",
                        None,
                    ),
                    "last_exception": repr(
                        getattr(
                            getattr(stop_runtime, "coordinator", None),
                            "last_exception",
                            None,
                        )
                    ),
                    "data": getattr(
                        getattr(stop_runtime, "coordinator", None),
                        "data",
                        None,
                    ),
                },
            }
            for stop_runtime in stop_runtimes
        ],
        "network_coordinator": {
            "last_update_success": getattr(
                network_coordinator,
                "last_update_success",
                None,
            ),
            "last_exception": repr(
                getattr(network_coordinator, "last_exception", None)
            ),
            "data": getattr(network_coordinator, "data", None),
        },
        "gtfs": {
            "loaded": gtfs is not None,
            "routes": len(gtfs.routes) if gtfs else 0,
            "stops": len(gtfs.stops) if gtfs else 0,
        },
    }
