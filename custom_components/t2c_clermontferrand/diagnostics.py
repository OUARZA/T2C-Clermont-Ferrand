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
    coordinator = getattr(domain_data, "coordinator", None)
    client = getattr(domain_data, "client", None)
    gtfs = getattr(client, "_gtfs", None)

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": dict(entry.data),
        },
        "coordinator": {
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "last_exception": repr(getattr(coordinator, "last_exception", None)),
            "data": getattr(coordinator, "data", None),
        },
        "gtfs": {
            "loaded": gtfs is not None,
            "routes": len(gtfs.routes) if gtfs else 0,
            "stops": len(gtfs.stops) if gtfs else 0,
        },
    }
