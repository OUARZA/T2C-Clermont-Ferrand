"""Regression tests for website departures (no Home Assistant runtime required)."""

import importlib
import json
import sys
import types
import unittest
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

# Import the API without executing the integration's Home Assistant bootstrap.
PACKAGE = "t2c_test_integration"
package = types.ModuleType(PACKAGE)
package.__path__ = [
    str(
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "t2c_clermontferrand"
    )
]
sys.modules[PACKAGE] = package
api = importlib.import_module(f"{PACKAGE}.api")
FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime.fromisoformat("2026-10-15T20:54:00+02:00").timestamp()


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def index():
    return api._GtfsIndex(
        routes={"B": api.T2CRoute("B", "B", "B"), "9": api.T2CRoute("9", "E4", "E4")},
        stops={},
        route_stops={},
        route_directions={},
        trip_routes={},
        trip_headsigns={},
        loaded_at=0,
    )


class DeparturesTests(unittest.TestCase):
    def parse(self, data, stop="CHAPB", direction="0", route="B", limit=20):
        with patch.object(api.time, "time", return_value=NOW):
            return api._parse_timetable_departures(
                data,
                index(),
                limit,
                stop_id=stop,
                direction_id=direction,
                route_id=route,
            )

    def test_chapelles_theoretical_despite_real_time_flag(self):
        result = self.parse(fixture("chap"))
        self.assertEqual(len(result), 3)
        for departure in result:
            item = departure.as_dict()
            self.assertEqual(item["destination"], "ROYAT Pl. Allard")
            self.assertFalse(item["realtime"])
            self.assertTrue(item["theoretical"])
            self.assertIsNone(item["estimated_at"])
            self.assertEqual(item["due_at"], item["scheduled_at"])
            self.assertTrue(item["due_at"].endswith("+02:00"))
        self.assertEqual(result[0].minutes, 5)

    def test_real_mixed_lists_jaude_and_gare(self):
        for name, stop in (("jaud", "JAUDB"), ("gasn", "GASNA")):
            with self.subTest(stop=stop):
                result = self.parse(fixture(name), stop=stop)
                self.assertEqual(len(result), 3)
                self.assertEqual([d.realtime for d in result], [True, False, False])
                self.assertEqual([d.theoretical for d in result], [False, True, True])
                self.assertEqual(result[0].due_at, result[0].estimated_at)
                self.assertNotEqual(result[0].due_at, result[0].scheduled_at)

    def test_line_platform_and_numeric_direction_filtering(self):
        data = fixture("jaud")
        self.assertEqual(len(self.parse(data, stop="JAUDB", route="9", direction=0)), 2)
        self.assertEqual(self.parse(data, stop="JAUDB", direction="1"), [])
        self.assertEqual(self.parse(data, stop="unknown"), [])
        self.assertEqual(self.parse(data, route="missing"), [])

    def test_intermediate_terminus_and_sort_before_limit(self):
        # Synthetic reordering of real records, with an intermediate terminus.
        data = fixture("jaud")
        line = next(x for x in data if x["route_id"] == "B")
        onward = [d for d in line["next_departures"] if d["stop_id"] == "JAUDS"]
        onward[0]["trip_headsign"] = "Jules Verne"
        onward[0]["real_time_stop_time"] = "2026-10-15T19:30:00Z"
        line["next_departures"] = list(reversed(onward))
        result = self.parse(data, stop="JAUDS", direction="1", limit=2)
        self.assertEqual(
            [d.destination for d in result], ["AULNAT St Exupéry", "Jules Verne"]
        )
        self.assertEqual([d.realtime for d in result], [False, True])
        self.assertLess(result[0].due_at.timestamp(), result[1].due_at.timestamp())

    def test_invalid_missing_unknown_and_no_data_estimates_fall_back(self):
        for status, estimate in (
            ("scheduled", None),
            ("scheduled", "bad"),
            ("no_data", "2026-10-15T19:00:00Z"),
            ("unknown", "2026-10-15T19:00:00Z"),
        ):
            data = fixture("chap")[:1]
            item = data[0]["next_departures"][0]
            data[0]["next_departures"] = [item]
            item.update(
                real_time_status=status,
                real_time_stop_time=estimate,
                real_time_delay=900,
            )
            result = self.parse(data)[0]
            self.assertFalse(result.realtime)
            self.assertIsNone(result.estimated_at)
            self.assertEqual(result.due_at, result.scheduled_at)

    def test_cancelled_and_skipped_normalized_for_existing_sensors(self):
        for status in ("cancelled", "skipped"):
            data = fixture("chap")[:1]
            item = data[0]["next_departures"][0]
            data[0]["next_departures"] = [item]
            item.update(
                real_time_status=status, real_time_stop_time="2026-10-15T19:10:00Z"
            )
            result = self.parse(data)[0]
            self.assertEqual(result.status, "cancelled")
            self.assertFalse(result.realtime)
            self.assertTrue(result.theoretical)
            self.assertIsNone(result.estimated_at)

    def test_empty_malformed_and_past(self):
        self.assertEqual(self.parse([]), [])
        self.assertEqual(self.parse([{"route_id": "B", "next_departures": []}]), [])
        for data in ({}, [{"route_id": "B"}], [{"next_departures": {}}]):
            with self.assertRaises(api.T2CDataError):
                self.parse(data)
        data = fixture("chap")
        with patch.object(api.time, "time", return_value=NOW + 86400):
            self.assertEqual(
                api._parse_timetable_departures(data, index(), 5, stop_id="CHAPB"), []
            )

    def test_timezone_offsets_and_winter(self):
        self.assertEqual(
            api._parse_t2c_datetime("2026-10-15T19:00:00Z").isoformat(),
            "2026-10-15T21:00:00+02:00",
        )
        self.assertEqual(
            api._parse_t2c_datetime("2026-12-15T19:00:00Z").isoformat(),
            "2026-12-15T20:00:00+01:00",
        )
        self.assertEqual(
            api._parse_t2c_datetime("2026-10-15T21:00:00+02:00"),
            api._parse_t2c_datetime("2026-10-15T19:00:00Z"),
        )

    def test_gtfs_parent_reference_not_identifier_truncation(self):
        content = BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("routes.txt", "route_id,route_short_name\nB,B\n")
            archive.writestr(
                "stops.txt",
                "stop_id,stop_name,parent_station\nCHAPB,Les Chapelles,CHAP\nODD-PLATFORM,Example,OTHER-PARENT\n",
            )
            archive.writestr(
                "trips.txt",
                "route_id,trip_id,trip_headsign,direction_id\nB,t,Royat,0\n",
            )
            archive.writestr("stop_times.txt", "trip_id,stop_id\nt,CHAPB\n")
        gtfs = api._parse_gtfs_zip(content.getvalue(), 0)
        self.assertEqual(
            gtfs.stop_parents, {"CHAPB": "CHAP", "ODD-PLATFORM": "OTHER-PARENT"}
        )


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_reference_fallback_and_fresh_encoded_datetime(self):
        client = api.T2CClient(None)
        client._async_get_gtfs = AsyncMock(return_value=index())
        client._async_get_json_list = AsyncMock(side_effect=[fixture("chapb"), [], []])
        first_request = datetime.now(api.T2C_TIME_ZONE)
        with patch.object(api, "datetime") as clock:
            clock.now.side_effect = [
                first_request,
                first_request + timedelta(seconds=1),
            ]
            for _ in range(2):
                await client.async_get_timetable_departures(
                    stop_id="CHAPB", limit=5, route_id="B", direction_id="0"
                )
        urls = [call.args[0] for call in client._async_get_json_list.call_args_list]
        self.assertTrue(urls[0].endswith("/CHAPB"))
        for url in urls[1:]:
            self.assertEqual(urlsplit(url).path, "/siv/stops/CHAP/routes/B/departures")
            self.assertEqual(parse_qs(urlsplit(url).query)["direction"], ["0"])
            self.assertIn("%2B", url)
            sent = datetime.fromisoformat(parse_qs(urlsplit(url).query)["dateTime"][0])
            self.assertLess(
                abs((datetime.now(api.T2C_TIME_ZONE) - sent).total_seconds()), 10
            )
        self.assertNotEqual(urls[1], urls[2])

    async def test_detailed_endpoint_fills_five_six_and_more(self):
        for name, stop_id, parent, direction, available in (
            ("chap_b_direction0", "CHAPB", "CHAP", "0", 6),
            ("jaud_b_direction1", "JAUDS", "JAUD", "1", 7),
        ):
            for limit in (5, 6, 20):
                with self.subTest(name=name, limit=limit):
                    client = api.T2CClient(None)
                    gtfs = index()
                    gtfs.stop_parents = {stop_id: parent}
                    client._async_get_gtfs = AsyncMock(return_value=gtfs)
                    client._async_get_json_list = AsyncMock(return_value=fixture(name))
                    with patch.object(api.time, "time", return_value=NOW):
                        result = await client.async_get_timetable_departures(
                            stop_id=stop_id,
                            route_id="B",
                            direction_id=direction,
                            limit=limit,
                        )
                    self.assertEqual(len(result), min(limit, available))
                    self.assertTrue(all(d["stop_id"] == stop_id for d in result))
                    self.assertEqual(
                        [d["due_at"] for d in result],
                        sorted(d["due_at"] for d in result),
                    )
                    self.assertNotIn(
                        "headline=", client._async_get_json_list.call_args.args[0]
                    )

    async def test_detailed_endpoint_empty_and_filtering(self):
        client = api.T2CClient(None)
        gtfs = index()
        gtfs.stop_parents = {"CHAPB": "CHAP"}
        client._async_get_gtfs = AsyncMock(return_value=gtfs)
        rows = fixture("chap_b_direction0")
        other_route = dict(rows[0], route_id="C")
        other_direction = dict(rows[0], trip_direction_id=1)
        other_platform = dict(rows[0], stop_id="CHAPS")
        intermediate = dict(rows[1], trip_headsign="Terminus intermédiaire")
        client._async_get_json_list = AsyncMock(
            return_value=[other_route, other_direction, other_platform, intermediate]
        )
        with patch.object(api.time, "time", return_value=NOW):
            result = await client.async_get_timetable_departures(
                stop_id="CHAPB",
                route_id="B",
                direction_id="0",
                limit=6,
            )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["destination"], "Terminus intermédiaire")
        client._async_get_json_list = AsyncMock(return_value=[])
        self.assertEqual(
            await client.async_get_timetable_departures(
                stop_id="CHAPB", route_id="B", limit=6
            ),
            [],
        )
        client._async_get_json_list = AsyncMock(
            side_effect=api.T2CConnectionError("offline")
        )
        with self.assertRaises(api.T2CConnectionError):
            await client.async_get_timetable_departures(
                stop_id="CHAPB", route_id="B", limit=6
            )

    async def test_gtfs_mapping_and_unresolved_parent(self):
        client = api.T2CClient(None)
        gtfs = index()
        gtfs.stop_parents = {"ODD": "PARENT"}
        client._async_get_gtfs = AsyncMock(return_value=gtfs)
        client._async_get_json_list = AsyncMock(return_value=[])
        self.assertEqual(
            await client.async_get_timetable_departures(stop_id="ODD", limit=5), []
        )
        self.assertIn(
            "/PARENT/departures?", client._async_get_json_list.call_args.args[0]
        )
        with self.assertRaises(api.T2CDataError):
            await client.async_get_timetable_departures(stop_id="UNKNOWN", limit=5)

    async def test_http_errors_and_invalid_top_level(self):
        class Response:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def raise_for_status(self):
                raise api.ClientError("HTTP 400 or 500")

        session = types.SimpleNamespace(get=lambda *a, **kw: Response())
        client = api.T2CClient(session)
        with self.assertRaises(api.T2CConnectionError):
            await client._async_get_json_list("https://example.invalid")
        with (
            patch.object(Response, "raise_for_status"),
            patch.object(Response, "json", new=AsyncMock(return_value={}), create=True),
            self.assertRaises(api.T2CDataError),
        ):
            await client._async_get_json_list("https://example.invalid")

    async def test_line_messages_reuse_official_alerts(self):
        client = api.T2CClient(None)
        client._async_get_json_list = AsyncMock(return_value=fixture("line_c_alerts"))
        alerts = await client.async_get_line_alerts("C")
        messages = api.line_alerts_to_messages(alerts, "C")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["id"], "1.33548.2")
        self.assertEqual(messages[1]["id"], "1.32583.2")
        self.assertIn("Charles de Gaulle", messages[0]["title"])
        for message in messages:
            self.assertEqual(message["scope"], "line")
            self.assertEqual(message["line_refs"], ["C"])
            self.assertEqual(message["stop_refs"], [])
            self.assertNotIn("<p>", message["content"])
            self.assertEqual(
                set(message),
                {
                    "id",
                    "title",
                    "content",
                    "valid_from",
                    "valid_until",
                    "line_refs",
                    "stop_refs",
                    "scope",
                },
            )
        client._async_get_json_list.assert_awaited_once_with(
            "https://api.t2c.fr/siv/alerts/by-line/C?type=Trafic"
        )
        self.assertEqual(api.line_alerts_to_messages([], "C"), [])

    async def test_missing_route_references_still_have_line_scope(self):
        alert = api._parse_line_alerts(fixture("line_c_alerts"))[0].as_dict()
        alert["affected_routes"] = []
        message = api.line_alerts_to_messages([alert], "C")[0]
        self.assertEqual(message["scope"], "line")
        self.assertEqual(message["line_refs"], ["C"])
        self.assertEqual(message["stop_refs"], [])


if __name__ == "__main__":
    unittest.main()
