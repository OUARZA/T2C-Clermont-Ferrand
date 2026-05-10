"""API client for T2C Clermont-Ferrand official GTFS feeds."""

from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO, TextIOWrapper
import logging
import re
import time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import zipfile

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    DATASET_API_URL,
    GTFS_RT_TRIP_UPDATES_URL,
    LINE_ALERTS_API_URL,
    QR_TIMETABLE_API_URL,
)

_LOGGER = logging.getLogger(__name__)

GTFS_CACHE_SECONDS = 12 * 60 * 60
HTTP_TIMEOUT = 20
MAX_STOP_OPTIONS = 500
T2C_TIME_ZONE = ZoneInfo("Europe/Paris")
NETWORK_MESSAGES_API_URL = "https://api.t2c.fr/siv/alerts/banners"


class T2CError(Exception):
    """Base T2C client error."""


class T2CConnectionError(T2CError):
    """Raised when official T2C data cannot be fetched."""


class T2CDataError(T2CError):
    """Raised when official T2C data cannot be parsed."""


@dataclass(slots=True, frozen=True)
class T2CRoute:
    """A T2C route from static GTFS."""

    route_id: str
    short_name: str
    long_name: str
    color: str | None = None
    text_color: str | None = None

    @property
    def label(self) -> str:
        """Return a route label suitable for Home Assistant selectors."""
        if self.long_name and self.long_name != self.short_name:
            return f"{self.short_name} - {self.long_name}"
        return self.short_name


@dataclass(slots=True, frozen=True)
class T2CStop:
    """A T2C stop served by a route."""

    stop_id: str
    name: str
    direction_id: str | None = None
    direction_name: str | None = None

    @property
    def label(self) -> str:
        """Return a stop label suitable for Home Assistant selectors."""
        if self.direction_name:
            return f"{self.name} -> {self.direction_name}"
        return self.name


@dataclass(slots=True, frozen=True)
class T2CDirection:
    """A T2C route direction from static GTFS."""

    direction_id: str
    name: str


@dataclass(slots=True, frozen=True)
class T2CDeparture:
    """A next departure parsed from GTFS-Realtime."""

    route_id: str | None
    route_name: str | None
    stop_id: str
    destination: str | None
    due_at: datetime
    minutes: int
    realtime: bool = True
    trip_id: str | None = None
    vehicle_id: str | None = None
    scheduled_at: datetime | None = None
    estimated_at: datetime | None = None
    status: str | None = None
    theoretical: bool | None = None
    info: str | None = None
    route_color: str | None = None
    route_text_color: str | None = None

    @property
    def label(self) -> str:
        """Return a readable departure label for sensor attributes."""
        route = self.route_name or "T2C"
        target = f" -> {self.destination}" if self.destination else ""
        if self.minutes == 0:
            return f"{route}{target}: a l'approche"
        return f"{route}{target}: {self.minutes} min"

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "route_id": self.route_id,
            "route_name": self.route_name,
            "stop_id": self.stop_id,
            "destination": self.destination,
            "due_at": self.due_at.isoformat(),
            "minutes": self.minutes,
            "realtime": self.realtime,
            "label": self.label,
            "trip_id": self.trip_id,
            "vehicle_id": self.vehicle_id,
            "scheduled_at": self.scheduled_at.isoformat()
            if self.scheduled_at
            else None,
            "estimated_at": self.estimated_at.isoformat()
            if self.estimated_at
            else None,
            "status": self.status,
            "theoretical": self.theoretical,
            "info": self.info,
            "route_color": self.route_color,
            "route_text_color": self.route_text_color,
        }


@dataclass(slots=True, frozen=True)
class T2CMessage:
    """An information message returned by the T2C timetable API."""

    message_id: str
    title: str
    content: str
    valid_from: str | None
    valid_until: str | None
    line_refs: list[str]
    stop_refs: list[str]

    @property
    def scope(self) -> str:
        """Return the message scope inferred from references."""
        if self.line_refs and self.stop_refs:
            return "line_and_stop"
        if self.line_refs:
            return "line"
        if self.stop_refs:
            return "stop"
        return "network"

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "id": self.message_id,
            "title": self.title,
            "content": self.content,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "line_refs": self.line_refs,
            "stop_refs": self.stop_refs,
            "scope": self.scope,
        }


@dataclass(slots=True, frozen=True)
class T2CLineAlert:
    """A line disruption returned by the T2C alerts API."""

    alert_id: str
    alert_type: str
    title: str
    text: str
    start_datetime: str | None
    end_datetime: str | None
    priority: int | None
    affected_routes: list[str]
    disruption_level: str | None
    created_at: str | None
    updated_at: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "id": self.alert_id,
            "type": self.alert_type,
            "title": self.title,
            "text": self.text,
            "start_datetime": self.start_datetime,
            "end_datetime": self.end_datetime,
            "priority": self.priority,
            "affected_routes": self.affected_routes,
            "disruption_level": self.disruption_level,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class _GtfsIndex:
    """Parsed static GTFS index used for selectors and trip metadata."""

    routes: dict[str, T2CRoute]
    stops: dict[str, str]
    route_stops: dict[str, list[T2CStop]]
    route_directions: dict[str, list[T2CDirection]]
    trip_routes: dict[str, str]
    trip_headsigns: dict[str, str]
    loaded_at: float


class T2CClient:
    """Client for the official T2C static GTFS and GTFS-Realtime feeds."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the client."""
        self._session = session
        self._gtfs: _GtfsIndex | None = None

    async def async_get_routes(self) -> list[T2CRoute]:
        """Return available T2C routes."""
        gtfs = await self._async_get_gtfs()
        routes = sorted(
            gtfs.routes.values(),
            key=lambda route: _natural_key(route.short_name),
        )
        _LOGGER.debug("Loaded %s T2C routes from GTFS", len(routes))
        return routes

    async def async_get_stops_for_route(self, route_id: str) -> list[T2CStop]:
        """Return stops served by a route."""
        return await self.async_get_stops_for_direction(route_id, None)

    async def async_get_directions_for_route(
        self,
        route_id: str,
    ) -> list[T2CDirection]:
        """Return directions served by a route."""
        gtfs = await self._async_get_gtfs()
        directions = gtfs.route_directions.get(route_id, [])
        _LOGGER.debug(
            "Loaded %s T2C directions for route %s",
            len(directions),
            route_id,
        )
        return directions

    async def async_get_stops_for_direction(
        self,
        route_id: str,
        direction_id: str | None,
    ) -> list[T2CStop]:
        """Return stops served by a route direction."""
        gtfs = await self._async_get_gtfs()
        matching_stops = [
            stop
            for stop in gtfs.route_stops.get(route_id, [])
            if direction_id is None or stop.direction_id == direction_id
        ]
        stops = _deduplicate_stops(matching_stops)
        _LOGGER.debug(
            "Loaded %s T2C stops for route %s direction %s",
            len(stops),
            route_id,
            direction_id,
        )
        return stops

    async def async_get_next_departures(
        self,
        *,
        stop_id: str,
        route_id: str | None = None,
        direction_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return next departures for a stop from GTFS-RT."""
        gtfs = await self._async_get_gtfs()
        payload = await self._async_get_bytes(GTFS_RT_TRIP_UPDATES_URL)
        departures = await asyncio.to_thread(
            _parse_gtfs_rt_trip_updates,
            payload,
            gtfs,
            stop_id,
            route_id,
            direction_id,
            limit,
        )
        _LOGGER.debug(
            "Parsed %s GTFS-RT departures for stop=%s route=%s direction=%s",
            len(departures),
            stop_id,
            route_id,
            direction_id,
        )
        return [departure.as_dict() for departure in departures]

    async def async_get_timetable_departures(
        self,
        *,
        stop_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Return next departures from the T2C timetable API."""
        data = await self._async_get_timetable(stop_id, limit)
        gtfs = await self._async_get_gtfs()
        departures = _parse_timetable_departures(data, gtfs, limit)
        _LOGGER.debug(
            "Parsed %s T2C timetable departures for stop=%s",
            len(departures),
            stop_id,
        )
        return [departure.as_dict() for departure in departures]

    async def async_get_stop_messages(
        self,
        *,
        stop_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Return information messages from the T2C timetable API."""
        data = await self._async_get_timetable(stop_id, limit)
        messages = _parse_timetable_messages(data)
        _LOGGER.debug(
            "Parsed %s T2C timetable messages for stop=%s",
            len(messages),
            stop_id,
        )
        return [message.as_dict() for message in messages]

    async def async_get_line_alerts(self, line_id: str) -> list[dict[str, Any]]:
        """Return traffic disruptions for a line from the T2C alerts API."""
        query = urlencode({"type": "Trafic"})
        url = f"{LINE_ALERTS_API_URL.format(line_id=line_id)}?{query}"
        data = await self._async_get_json_list(url)
        alerts = _parse_line_alerts(data)
        _LOGGER.debug(
            "Parsed %s T2C line alerts for line=%s",
            len(alerts),
            line_id,
        )
        return [alert.as_dict() for alert in alerts]

    async def async_get_network_messages(self) -> list[dict[str, Any]]:
        """Return network information from the T2C alerts API."""
        data = await self._async_get_json_list(NETWORK_MESSAGES_API_URL)
        messages = _parse_line_alerts(data)
        _LOGGER.debug("Parsed %s T2C network messages", len(messages))
        return [message.as_dict() for message in messages]

    async def _async_get_timetable(self, stop_id: str, limit: int) -> dict[str, Any]:
        """Fetch the T2C timetable API for a stop."""
        query = urlencode({"_stop_code": stop_id, "_limit": limit})
        return await self._async_get_json(f"{QR_TIMETABLE_API_URL}?{query}")

    async def _async_get_gtfs(self) -> _GtfsIndex:
        """Return a cached static GTFS index."""
        now = time.monotonic()
        if self._gtfs and now - self._gtfs.loaded_at < GTFS_CACHE_SECONDS:
            return self._gtfs

        metadata = await self._async_get_json(DATASET_API_URL)
        static_url = _extract_static_gtfs_url(metadata)
        gtfs_zip = await self._async_get_bytes(static_url)
        self._gtfs = await asyncio.to_thread(_parse_gtfs_zip, gtfs_zip, now)
        _LOGGER.debug(
            "Built T2C GTFS index: routes=%s stops=%s",
            len(self._gtfs.routes),
            len(self._gtfs.stops),
        )
        return self._gtfs

    async def _async_get_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON from an official data endpoint."""
        try:
            async with self._session.get(url, timeout=HTTP_TIMEOUT) as response:
                response.raise_for_status()
                return await response.json()
        except (ClientError, ClientResponseError, TimeoutError) as err:
            raise T2CConnectionError(f"Unable to fetch JSON from {url}") from err

    async def _async_get_json_list(self, url: str) -> list[dict[str, Any]]:
        """Fetch a JSON list from an official data endpoint."""
        try:
            async with self._session.get(url, timeout=HTTP_TIMEOUT) as response:
                response.raise_for_status()
                data = await response.json()
        except (ClientError, ClientResponseError, TimeoutError) as err:
            raise T2CConnectionError(f"Unable to fetch JSON from {url}") from err

        if not isinstance(data, list):
            raise T2CDataError(f"Unexpected JSON payload from {url}")

        return data

    async def _async_get_bytes(self, url: str) -> bytes:
        """Fetch bytes from an official data endpoint."""
        try:
            async with self._session.get(url, timeout=HTTP_TIMEOUT) as response:
                response.raise_for_status()
                return await response.read()
        except (ClientError, ClientResponseError, TimeoutError) as err:
            raise T2CConnectionError(f"Unable to fetch bytes from {url}") from err


def _parse_gtfs_rt_trip_updates(
    payload: bytes,
    gtfs: _GtfsIndex,
    stop_id: str,
    route_id: str | None,
    direction_id: str | None,
    limit: int,
) -> list[T2CDeparture]:
    """Parse a GTFS-Realtime FeedMessage and return matching departures."""
    from google.transit import gtfs_realtime_pb2

    feed = gtfs_realtime_pb2.FeedMessage()

    try:
        feed.ParseFromString(payload)
    except Exception as err:  # noqa: BLE001 - protobuf parse exceptions vary
        raise T2CDataError("Unable to parse T2C GTFS-Realtime FeedMessage") from err

    now_ts = int(time.time())
    departures: list[T2CDeparture] = []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        trip_update = entity.trip_update
        trip = trip_update.trip
        trip_route_id = trip.route_id or gtfs.trip_routes.get(trip.trip_id)

        if route_id and trip_route_id and trip_route_id != route_id:
            continue
        if (
            direction_id
            and trip.HasField("direction_id")
            and str(trip.direction_id) != direction_id
        ):
            continue

        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id != stop_id:
                continue

            due_ts = _extract_stop_time(stop_time_update)
            if due_ts is None or due_ts < now_ts - 60:
                continue

            route = gtfs.routes.get(trip_route_id or "")
            due_at = datetime.fromtimestamp(due_ts, UTC)
            departures.append(
                T2CDeparture(
                    route_id=trip_route_id,
                    route_name=route.short_name if route else None,
                    route_color=route.color if route else None,
                    route_text_color=route.text_color if route else None,
                    stop_id=stop_id,
                    destination=gtfs.trip_headsigns.get(trip.trip_id),
                    due_at=due_at,
                    minutes=max(0, round((due_ts - now_ts) / 60)),
                    realtime=True,
                    trip_id=trip.trip_id or None,
                    vehicle_id=trip_update.vehicle.id or None,
                )
            )

    departures.sort(key=lambda departure: departure.due_at)
    return departures[:limit]


def _parse_timetable_messages(data: dict[str, Any]) -> list[T2CMessage]:
    """Parse information messages from the T2C timetable JSON API."""
    messages: list[T2CMessage] = []

    for item in data.get("message", []):
        title = item.get("title")
        content = item.get("content")

        if not title or not content:
            continue

        messages.append(
            T2CMessage(
                message_id=str(item.get("id") or ""),
                title=str(title),
                content=str(content),
                valid_from=item.get("valid_start_time"),
                valid_until=item.get("valid_until_time"),
                line_refs=list(item.get("list_line_ref") or []),
                stop_refs=list(item.get("list_stop_point_ref") or []),
            )
        )

    return messages


def _parse_timetable_departures(
    data: dict[str, Any],
    gtfs: _GtfsIndex,
    limit: int,
) -> list[T2CDeparture]:
    """Parse departures from the T2C timetable JSON API."""
    departures: list[T2CDeparture] = []
    now_ts = int(time.time())

    for item in data.get("timetable", {}).get("timetable", []):
        due_at = _parse_t2c_datetime(
            item.get("datetime_estimated") or item.get("datetime")
        )
        if due_at is None:
            continue

        scheduled_at = _parse_t2c_datetime(item.get("datetime"))
        estimated_at = _parse_t2c_datetime(item.get("datetime_estimated"))
        minutes = max(0, round((int(due_at.timestamp()) - now_ts) / 60))
        status = item.get("departure_status")
        theoretical = item.get("theorique")
        info = item.get("info")
        line_ref = item.get("line_id")
        route = _find_route(gtfs, line_ref)

        departures.append(
            T2CDeparture(
                route_id=route.route_id if route else line_ref,
                route_name=route.short_name if route else line_ref,
                route_color=route.color if route else None,
                route_text_color=route.text_color if route else None,
                stop_id=data.get("referential_parameter", {}).get("stop_id", ""),
                destination=item.get("destination"),
                due_at=due_at,
                minutes=minutes,
                realtime=estimated_at is not None and theoretical is False,
                scheduled_at=scheduled_at,
                estimated_at=estimated_at,
                status=status,
                theoretical=theoretical,
                info=info,
            )
        )

    return departures[:limit]


def _find_route(gtfs: _GtfsIndex, line_ref: str | None) -> T2CRoute | None:
    """Return a route from a GTFS route ID or public short name."""
    if not line_ref:
        return None

    if route := gtfs.routes.get(line_ref):
        return route

    return next(
        (route for route in gtfs.routes.values() if route.short_name == line_ref),
        None,
    )


def _parse_line_alerts(data: list[dict[str, Any]]) -> list[T2CLineAlert]:
    """Parse line disruption alerts from the T2C alerts API."""
    alerts: list[T2CLineAlert] = []

    for item in data:
        title = item.get("title")
        text = item.get("text")

        if not title or not text:
            continue

        alerts.append(
            T2CLineAlert(
                alert_id=str(item.get("id") or ""),
                alert_type=str(item.get("type") or ""),
                title=str(title),
                text=_html_to_text(str(text)),
                start_datetime=item.get("start_datetime"),
                end_datetime=item.get("end_datetime"),
                priority=item.get("priority"),
                affected_routes=list(item.get("affected_routes") or []),
                disruption_level=item.get("disruption_level"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )
        )

    return alerts


def _extract_static_gtfs_url(metadata: dict[str, Any]) -> str:
    """Extract the static GTFS ZIP URL from data.gouv.fr metadata."""
    candidates: list[tuple[int, str]] = []

    for resource in metadata.get("resources", []):
        format_value = str(resource.get("format") or "").lower()
        mime = str(resource.get("mime") or "").lower()
        title = str(resource.get("title") or resource.get("description") or "").lower()
        resource_type = str(resource.get("type") or "").lower()
        url = resource.get("latest") or resource.get("url")

        if not url:
            continue

        is_static_gtfs = (
            title == "gtfs"
            or format_value == "gtfs"
            or (format_value == "zip" and "gtfs" in title)
            or (mime == "application/zip" and "gtfs" in title)
        )
        if not is_static_gtfs:
            continue

        score = 20 if resource_type == "main" else 0
        score += 10 if mime == "application/zip" or format_value == "zip" else 0
        candidates.append((score, url))

    if not candidates:
        raise T2CDataError("Unable to find T2C static GTFS resource")

    candidates.sort(reverse=True)
    return candidates[0][1]


def _parse_gtfs_zip(payload: bytes, loaded_at: float) -> _GtfsIndex:
    """Parse static GTFS bytes into a compact route and stop index."""
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            routes = _read_routes(archive)
            stops = _read_stops(archive)
            trip_routes, trip_headsigns, trip_directions = _read_trips(archive)
            route_directions = _build_route_directions(
                trip_routes,
                trip_headsigns,
                trip_directions,
            )
            route_stops = _read_route_stops(
                archive,
                routes=routes,
                stops=stops,
                trip_routes=trip_routes,
                trip_headsigns=trip_headsigns,
                trip_directions=trip_directions,
            )
    except (KeyError, zipfile.BadZipFile, csv.Error) as err:
        raise T2CDataError("Unable to parse T2C static GTFS ZIP") from err

    return _GtfsIndex(
        routes=routes,
        stops=stops,
        route_stops=route_stops,
        route_directions=route_directions,
        trip_routes=trip_routes,
        trip_headsigns=trip_headsigns,
        loaded_at=loaded_at,
    )


def _read_routes(archive: zipfile.ZipFile) -> dict[str, T2CRoute]:
    """Read routes.txt from a GTFS archive."""
    return {
        row["route_id"]: T2CRoute(
            route_id=row["route_id"],
            short_name=row.get("route_short_name") or row["route_id"],
            long_name=row.get("route_long_name") or "",
            color=_format_hex_color(row.get("route_color")),
            text_color=_format_hex_color(row.get("route_text_color")),
        )
        for row in _read_csv(archive, "routes.txt")
    }


def _format_hex_color(value: str | None) -> str | None:
    """Return a CSS-ready hex color from a GTFS color value."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    return value if value.startswith("#") else f"#{value}"


def _read_stops(archive: zipfile.ZipFile) -> dict[str, str]:
    """Read stops.txt from a GTFS archive."""
    return {
        row["stop_id"]: row.get("stop_name") or row["stop_id"]
        for row in _read_csv(archive, "stops.txt")
    }


def _read_trips(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Read trips.txt from a GTFS archive."""
    trip_routes: dict[str, str] = {}
    trip_headsigns: dict[str, str] = {}
    trip_directions: dict[str, str] = {}

    for row in _read_csv(archive, "trips.txt"):
        trip_id = row["trip_id"]
        trip_routes[trip_id] = row["route_id"]
        if headsign := row.get("trip_headsign"):
            trip_headsigns[trip_id] = headsign
        if direction_id := row.get("direction_id"):
            trip_directions[trip_id] = direction_id

    return trip_routes, trip_headsigns, trip_directions


def _build_route_directions(
    trip_routes: dict[str, str],
    trip_headsigns: dict[str, str],
    trip_directions: dict[str, str],
) -> dict[str, list[T2CDirection]]:
    """Build route direction choices from GTFS trips."""
    by_route: dict[str, dict[str, T2CDirection]] = {}

    for trip_id, route_id in trip_routes.items():
        direction_id = trip_directions.get(trip_id, "")
        headsign = trip_headsigns.get(trip_id)

        if not direction_id or not headsign:
            continue

        by_route.setdefault(route_id, {}).setdefault(
            direction_id,
            T2CDirection(direction_id=direction_id, name=headsign),
        )

    return {
        route_id: sorted(directions.values(), key=lambda direction: direction.name)
        for route_id, directions in by_route.items()
    }


def _read_route_stops(
    archive: zipfile.ZipFile,
    *,
    routes: dict[str, T2CRoute],
    stops: dict[str, str],
    trip_routes: dict[str, str],
    trip_headsigns: dict[str, str],
    trip_directions: dict[str, str],
) -> dict[str, list[T2CStop]]:
    """Read stop_times.txt and build route stop choices."""
    seen: set[tuple[str, str, str, str]] = set()
    collected: dict[str, list[T2CStop]] = {route_id: [] for route_id in routes}

    for row in _read_csv(archive, "stop_times.txt"):
        trip_id = row["trip_id"]
        route_id = trip_routes.get(trip_id)
        stop_id = row["stop_id"]

        if not route_id or stop_id not in stops:
            continue

        direction_id = trip_directions.get(trip_id, "")
        direction_name = trip_headsigns.get(trip_id, "")
        key = (route_id, stop_id, direction_id, direction_name)

        if key in seen:
            continue

        seen.add(key)
        collected.setdefault(route_id, []).append(
            T2CStop(
                stop_id=stop_id,
                name=stops[stop_id],
                direction_id=direction_id or None,
                direction_name=direction_name or None,
            )
        )

    for route_id, route_stops in collected.items():
        route_stops.sort(key=lambda stop: _natural_key(stop.label))
        collected[route_id] = route_stops[:MAX_STOP_OPTIONS]

    return collected


def _deduplicate_stops(stops: list[T2CStop]) -> list[T2CStop]:
    """Return one selector option per physical stop."""
    deduplicated: dict[str, T2CStop] = {}

    for stop in stops:
        deduplicated.setdefault(
            stop.stop_id,
            T2CStop(stop_id=stop.stop_id, name=stop.name),
        )

    return sorted(
        deduplicated.values(),
        key=lambda stop: _natural_key(stop.name),
    )[:MAX_STOP_OPTIONS]


def _read_csv(archive: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    """Read a CSV file from a GTFS archive."""
    with archive.open(filename) as raw_file:
        text_file = TextIOWrapper(raw_file, encoding="utf-8-sig")
        return list(csv.DictReader(text_file))


def _extract_stop_time(stop_time_update: Any) -> int | None:
    """Extract the best timestamp from a GTFS-RT StopTimeUpdate."""
    if stop_time_update.HasField("departure") and stop_time_update.departure.time:
        return stop_time_update.departure.time
    if stop_time_update.HasField("arrival") and stop_time_update.arrival.time:
        return stop_time_update.arrival.time
    return None


def _parse_t2c_datetime(value: Any) -> datetime | None:
    """Parse a T2C local datetime value."""
    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return parsed.replace(tzinfo=T2C_TIME_ZONE)


def _natural_key(value: str) -> list[int | str]:
    """Sort labels naturally."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def _html_to_text(value: str) -> str:
    """Convert the limited HTML returned by T2C alerts to plain text."""
    parser = _HTMLTextExtractor()
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+", " ", parser.text).strip()


class _HTMLTextExtractor(HTMLParser):
    """Small HTML text extractor for T2C alert bodies."""

    def __init__(self) -> None:
        """Initialize the parser."""
        super().__init__()
        self._parts: list[str] = []

    @property
    def text(self) -> str:
        """Return extracted text."""
        return "".join(self._parts)

    def handle_data(self, data: str) -> None:
        """Handle text nodes."""
        self._parts.append(data)

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Handle tags that should add spacing."""
        if tag in {"br", "p", "li"}:
            self._parts.append(" ")
