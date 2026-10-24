"""Frontend lifecycle tests using HA API boundary doubles, not a HA runtime."""

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


class Resources:
    def __init__(self, items=()):
        self.items = [dict(item) for item in items]
        self.loaded = False
        self.mutations = 0

    async def async_get_info(self):
        await asyncio.sleep(0)
        self.loaded = True

    def async_items(self):
        assert self.loaded
        return self.items

    async def async_create_item(self, data):
        await asyncio.sleep(0)
        self.items.append(
            {"id": "created", "url": data["url"], "type": data["res_type"]}
        )
        self.mutations += 1

    async def async_update_item(self, item_id, data):
        await asyncio.sleep(0)
        item = next(item for item in self.items if item["id"] == item_id)
        item.update(url=data["url"], type=data["res_type"])
        self.mutations += 1

    async def async_delete_item(self, item_id):
        self.items = [item for item in self.items if item["id"] != item_id]
        self.mutations += 1


def load_frontend():
    package = types.ModuleType("t2c_frontend_test")
    package.__path__ = [
        str(
            Path(__file__).resolve().parents[1]
            / "custom_components/t2c_clermontferrand"
        )
    ]
    modules = {"t2c_frontend_test": package}
    for name in (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.http",
        "homeassistant.components.lovelace",
        "homeassistant.components.lovelace.const",
        "homeassistant.components.lovelace.resources",
        "homeassistant.core",
    ):
        modules[name] = types.ModuleType(name)
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.components.http"].StaticPathConfig = lambda *args, **kwargs: (
        args,
        kwargs,
    )
    modules["homeassistant.components.lovelace.const"].LOVELACE_DATA = "lovelace"
    modules[
        "homeassistant.components.lovelace.resources"
    ].ResourceStorageCollection = Resources
    with patch.dict(sys.modules, modules):
        return importlib.import_module("t2c_frontend_test.frontend")


frontend = load_frontend()


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    def hass(self, resources):
        return types.SimpleNamespace(
            data={"lovelace": types.SimpleNamespace(resources=resources)},
            http=types.SimpleNamespace(async_register_static_paths=AsyncMock()),
            async_add_executor_job=AsyncMock(side_effect=lambda fn: fn()),
        )

    async def test_concurrent_entries_reload_and_last_entry_unload(self):
        resources = Resources()
        hass = self.hass(resources)
        await asyncio.gather(*(frontend.async_setup_frontend(hass) for _ in range(10)))
        # Domain runtime removal on last entry unload must not remove route state.
        hass.data.pop("t2c_clermontferrand", None)
        await frontend.async_setup_frontend(hass)
        hass.http.async_register_static_paths.assert_awaited_once()
        self.assertEqual(len(resources.items), 1)
        self.assertEqual(resources.mutations, 1)
        self.assertEqual(resources.items[0]["type"], "module")

    async def test_migrate_all_known_paths_preserve_unrelated_resources(self):
        items = [
            {"id": str(i), "url": url + "?hacstag=123#fragment", "type": "js"}
            for i, url in enumerate(sorted(frontend.LEGACY_PATHS))
        ]
        other = {"id": "other", "url": "/hacsfiles/another/card.js", "type": "module"}
        resources = Resources([*items, other])
        hass = self.hass(resources)
        await frontend.async_setup_frontend(hass)
        self.assertEqual(len(resources.items), 2)
        self.assertIn(other, resources.items)
        self.assertEqual(resources.items[0]["id"], items[0]["id"])
        self.assertTrue(
            resources.items[0]["url"].startswith(frontend.RESOURCE_PATH + "?v=")
        )
        self.assertEqual(resources.items[0]["type"], "module")

    async def test_update_version_and_prefer_existing_canonical_id(self):
        resources = Resources(
            [
                {
                    "id": "old",
                    "url": next(iter(frontend.LEGACY_PATHS)),
                    "type": "module",
                },
                {"id": "keep", "url": frontend.RESOURCE_PATH + "?v=old", "type": "js"},
                {"id": "duplicate", "url": frontend.RESOURCE_PATH, "type": "module"},
            ]
        )
        hass = self.hass(resources)
        await frontend.async_setup_frontend(hass)
        self.assertEqual([item["id"] for item in resources.items], ["keep"])
        self.assertNotIn("v=old", resources.items[0]["url"])
        changes = resources.mutations
        await frontend.async_setup_frontend(hass)
        self.assertEqual(resources.mutations, changes)

    async def test_yaml_is_untouched(self):
        yaml = types.SimpleNamespace(
            data=[{"url": next(iter(frontend.LEGACY_PATHS)), "type": "module"}]
        )
        original = list(yaml.data)
        hass = self.hass(yaml)
        with self.assertLogs(frontend._LOGGER, level="WARNING") as logs:
            await frontend.async_setup_frontend(hass)
        self.assertEqual(yaml.data, original)
        self.assertIn("type: module", logs.output[0])
        hass.http.async_register_static_paths.assert_awaited_once()

    async def test_static_failure_retries_without_duplicate_registration(self):
        hass = self.hass(Resources())
        hass.http.async_register_static_paths.side_effect = [
            RuntimeError("temporary"),
            None,
        ]
        with self.assertRaises(RuntimeError):
            await frontend.async_setup_frontend(hass)
        await frontend.async_setup_frontend(hass)
        await frontend.async_setup_frontend(hass)
        self.assertEqual(hass.http.async_register_static_paths.await_count, 2)
        self.assertEqual(len(hass.data["lovelace"].resources.items), 1)

    async def test_update_failure_does_not_delete_legacy_items(self):
        resources = Resources(
            [
                {"id": str(i), "url": url, "type": "module"}
                for i, url in enumerate(frontend.LEGACY_PATHS)
            ]
        )
        original = [dict(item) for item in resources.items]
        resources.async_update_item = AsyncMock(side_effect=RuntimeError("storage"))
        with self.assertRaises(RuntimeError):
            await frontend.async_setup_frontend(self.hass(resources))
        self.assertEqual(resources.items, original)

    def test_precise_matching(self):
        for url in frontend.LEGACY_PATHS | {frontend.RESOURCE_PATH}:
            self.assertTrue(frontend.is_card_resource(url + "?v=123"))
            self.assertFalse(frontend.is_card_resource("https://example.org" + url))
            self.assertFalse(frontend.is_card_resource("//example.org" + url))
            self.assertFalse(frontend.is_card_resource(url + ".backup"))
        self.assertFalse(frontend.is_card_resource("http://[invalid"))
        self.assertFalse(frontend.is_card_resource("/local/other/" + frontend.FILENAME))

    def test_hash_changes_with_actual_bytes(self):
        with patch.object(Path, "read_bytes", return_value=b"first"):
            first = frontend._resource_url()
        with patch.object(Path, "read_bytes", return_value=b"second"):
            self.assertNotEqual(first, frontend._resource_url())
