"""Small client for T2C Clermont-Ferrand."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from typing import Any
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup


BASE_QR_URL = "http://qr.t2c.fr/qrcode"


@dataclass(slots=True)
class Passage:
    """Represents one next passage."""

    label: str
    minutes: int | None = None


class T2CClient:
    """Client for public T2C pages."""

    async def async_get_next_passages(self, stop_id: str) -> list[dict[str, Any]]:
        """Return next passages for a stop id."""
        return await asyncio.to_thread(self.get_next_passages, stop_id)

    def get_next_passages(self, stop_id: str) -> list[dict[str, Any]]:
        """Return next passages for a stop id."""
        url = f"{BASE_QR_URL}?{urllib.parse.urlencode({'_stop_id': stop_id})}"

        with urllib.request.urlopen(url, timeout=15) as response:
            html = response.read()

        soup = BeautifulSoup(html, "html.parser")
        text_lines = [
            line.strip()
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

        passages: list[dict[str, Any]] = []

        for line in text_lines:
            lower = line.lower()

            if "min" not in lower and "heure" not in lower and "h" not in lower:
                continue

            minutes = self._extract_minutes(line)
            passages.append(
                {
                    "label": line,
                    "minutes": minutes,
                }
            )

        return passages[:5]

    @staticmethod
    def _extract_minutes(value: str) -> int | None:
        """Extract a minute value from a label when possible."""
        match = re.search(r"(\d+)\s*min", value, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Handles HH:MM-like values by returning None.
        return None
