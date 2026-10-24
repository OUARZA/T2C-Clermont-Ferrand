"""Polling regression tests with lightweight Home Assistant boundary stubs."""

import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

from test_api import PACKAGE, api, fixture


class CoordinatorBase:
    @classmethod
    def __class_getitem__(cls, item):
        return cls


class UpdateFailed(Exception):
    pass


def load_coordinator():
    modules = {}
    for name in (
        "homeassistant",
        "homeassistant.config_entries",
        "homeassistant.core",
        "homeassistant.helpers",
        "homeassistant.helpers.update_coordinator",
    ):
        modules[name] = types.ModuleType(name)
    modules["homeassistant.config_entries"].ConfigEntry = object
    modules["homeassistant.core"].HomeAssistant = object
    modules[
        "homeassistant.helpers.update_coordinator"
    ].DataUpdateCoordinator = CoordinatorBase
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = UpdateFailed
    with patch.dict(sys.modules, modules):
        return importlib.import_module(f"{PACKAGE}.coordinator")


coordinator_module = load_coordinator()


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def coordinator(self, departures):
        client = api.T2CClient(None)
        client.async_get_timetable_departures = AsyncMock(return_value=departures)
        client.async_get_line_alerts = AsyncMock(
            return_value=[
                item.as_dict()
                for item in api._parse_line_alerts(fixture("line_c_alerts"))
            ]
        )
        coordinator = object.__new__(coordinator_module.T2CDataUpdateCoordinator)
        coordinator.client = client
        coordinator.entry = types.SimpleNamespace(data={"departure_limit": 5})
        coordinator.stop_data = {
            "stop_id": "JAUDB",
            "line_id": "C",
            "direction_id": "0",
        }
        return coordinator

    async def test_single_alert_request_feeds_messages_and_departures(self):
        coordinator = self.coordinator(
            [{"route_id": "C", "destination": "DURTOL Clinique"}]
        )
        result = await coordinator._async_update_data()
        coordinator.client.async_get_line_alerts.assert_awaited_once_with("C")
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][0]["scope"], "line")
        self.assertTrue(result["departures"][0]["has_alert"])
        self.assertEqual(len(result["departures"][0]["line_alerts"]), 2)
        self.assertEqual(
            result["departures"][0]["alert_title"], result["messages"][0]["title"]
        )

    async def test_messages_available_without_departures(self):
        coordinator = self.coordinator([])
        result = await coordinator._async_update_data()
        self.assertEqual(result["departures"], [])
        self.assertEqual(len(result["messages"]), 2)
        coordinator.client.async_get_line_alerts.assert_awaited_once_with("C")

    async def test_alert_error_does_not_hide_departures(self):
        coordinator = self.coordinator(
            [{"route_id": "C", "destination": "DURTOL Clinique"}]
        )
        coordinator.client.async_get_line_alerts.side_effect = api.T2CConnectionError(
            "offline"
        )
        result = await coordinator._async_update_data()
        self.assertEqual(result["messages"], [])
        self.assertEqual(result["alerts"], [])
        self.assertEqual(len(result["departures"]), 1)
        self.assertFalse(result["departures"][0]["has_alert"])

    async def test_no_departures_keeps_alerts_and_recovers(self):
        coordinator = self.coordinator([])
        coordinator.client.async_get_timetable_departures.side_effect = (
            api.T2CNoDeparturesError("No departures")
        )
        result = await coordinator._async_update_data()
        self.assertTrue(result["no_departures"])
        self.assertEqual(result["departures"], [])
        self.assertEqual(len(result["alerts"]), 2)
        self.assertEqual(len(result["messages"]), 2)
        coordinator.client.async_get_timetable_departures.side_effect = None
        coordinator.client.async_get_timetable_departures.return_value = [{"route_id": "C"}]
        result = await coordinator._async_update_data()
        self.assertFalse(result["no_departures"])
        self.assertEqual(len(result["departures"]), 1)
        coordinator.client.async_get_timetable_departures.side_effect = api.T2CConnectionError("offline")
        with self.assertRaises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_network_messages_unchanged(self):
        client = api.T2CClient(None)
        client._async_get_json_list = AsyncMock(return_value=fixture("line_c_alerts"))
        await client.async_get_network_messages()
        client._async_get_json_list.assert_awaited_once_with(
            "https://api.t2c.fr/siv/alerts/banners"
        )


class LineAlertScopeTests(unittest.TestCase):
    def test_other_direction_alert_kept_only_on_its_line(self):
        alert = {
            "id": "1.33755.2",
            "title": "Arrêt INSPÉ Chamalières direction Zone des Gravanches reporté le 19 octobre 2026",
            "text": "Arrêt reporté au 30 boulevard Pasteur.",
            "affected_routes": ["10"],
        }
        departures = [
            {"route_id": "10", "destination": "Jules Verne", "stop_id": "INCHR"},
            {"route_id": "10", "destination": "Zone des Gravanches"},
            {"route_id": "C", "destination": "DURTOL Clinique"},
        ]
        result = coordinator_module._attach_line_alerts_to_departures(
            departures,
            {"10": [alert]},
        )
        for departure in result[:2]:
            self.assertTrue(departure["has_alert"])
            self.assertEqual(departure["line_alerts"], [alert])
            self.assertEqual(departure["alert_title"], alert["title"])
            self.assertEqual(departure["alert_icon"], "mdi:alert-circle")
        self.assertFalse(result[2]["has_alert"])
        self.assertEqual(result[2]["line_alerts"], [])
        self.assertIsNone(result[2]["alert_title"])
        self.assertNotIn("has_alert", departures[0])
