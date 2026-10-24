"""Serve and migrate the bundled Lovelace module.

The lifecycle state deliberately survives config entry unloads: HTTP routes cannot
be unregistered, and another entry (or a reload) must reuse the same route.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
DATA_FRONTEND = "t2c_clermontferrand_frontend"
FILENAME = "t2c_clermont-ferrand_card.js"
STATIC_URL = "/t2c_clermontferrand"
RESOURCE_PATH = f"{STATIC_URL}/{FILENAME}"
WWW = Path(__file__).parent / "www"
# Exact paths documented by the former card repository. Never match a basename
# alone, external origins, or another card's similarly named directory.
LEGACY_PATHS = frozenset(
    {
        f"/hacsfiles/T2C-Clermont-Ferrand-Card/{FILENAME}",
        f"/local/community/T2C-Clermont-Ferrand-Card/{FILENAME}",
        f"/local/community/t2c_clermontferrand_card/{FILENAME}",
        f"/local/community/t2c_clermontferrand_card/dist/{FILENAME}",
    }
)


@dataclass
class FrontendState:
    """One lock and one static registration per Home Assistant process."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    registered: bool = False
    url: str | None = None


def is_card_resource(url: str) -> bool:
    """Recognize only this integration's resource and known legacy paths."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return not (parts.scheme or parts.netloc) and parts.path in (
        LEGACY_PATHS | {RESOURCE_PATH}
    )


def _resource_url() -> str:
    """Hash actual bytes, so even development builds invalidate the cache."""
    digest = hashlib.sha256((WWW / FILENAME).read_bytes()).hexdigest()[:16]
    return f"{RESOURCE_PATH}?v={digest}"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Set up the route once and reconcile resources for every entry setup."""
    state = hass.data.setdefault(DATA_FRONTEND, FrontendState())
    async with state.lock:
        if state.url is None:
            state.url = await hass.async_add_executor_job(_resource_url)
        if not state.registered:
            await hass.http.async_register_static_paths(
                [StaticPathConfig(STATIC_URL, str(WWW), cache_headers=False)]
            )
            state.registered = True

        resources = hass.data[LOVELACE_DATA].resources
        if not isinstance(resources, ResourceStorageCollection):
            _LOGGER.warning(
                "T2C Lovelace resources are managed in YAML. Replace only the old "
                "T2C card resource with %s (type: module), remove T2C duplicates, "
                "then reload resources and fully refresh all browsers. "
                "No YAML file has been modified. See the migration README.",
                state.url,
            )
            return

        # Public method ensures storage has loaded before inspecting async_items.
        await resources.async_get_info()
        matching = [
            item
            for item in resources.async_items()
            if is_card_resource(item.get("url", ""))
        ]
        # Prefer the canonical item and preserve its ID. Upgrade a legacy item
        # in place otherwise. Do not delete anything until the update succeeds.
        canonical = next(
            (item for item in matching if urlsplit(item["url"]).path == RESOURCE_PATH),
            matching[0] if matching else None,
        )
        if canonical is None:
            await resources.async_create_item({"url": state.url, "res_type": "module"})
        else:
            if canonical["url"] != state.url or canonical.get("type") != "module":
                await resources.async_update_item(
                    canonical["id"], {"url": state.url, "res_type": "module"}
                )
            for item in matching:
                if item["id"] != canonical["id"]:
                    await resources.async_delete_item(item["id"])
