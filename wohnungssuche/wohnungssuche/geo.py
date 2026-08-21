"""Geo helpers: distance, district detection and (optional) geocoding.

Distances are computed with the haversine formula.  Coordinates come from one
of three sources, cheapest first:

1. coordinates the scraper already found in the page,
2. a built-in table of Wiesbaden district centroids (works offline),
3. Nominatim (OpenStreetMap), rate-limited to 1 request/second per their usage
   policy, and only if ``allow_network`` is enabled.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
import unicodedata
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

LOGGER = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = (
    "wohnungssuche-wiesbaden/2.0 (private apartment search; contact via GitHub)"
)

# Centroids of Wiesbaden's Ortsbezirke, good enough for a 4 km radius check.
DISTRICT_COORDS: Dict[str, Tuple[float, float]] = {
    "Mitte": (50.0826, 8.2400),
    "Innenstadt": (50.0826, 8.2400),
    "Nordost": (50.0930, 8.2500),
    "Suedost": (50.0700, 8.2600),
    "Rheingauviertel": (50.0680, 8.2260),
    "Hollerborn": (50.0700, 8.2200),
    "Westend": (50.0850, 8.2300),
    "Bleichstrasse": (50.0800, 8.2350),
    "Suedwest": (50.0650, 8.2200),
    "Biebrich": (50.0400, 8.2300),
    "Dotzheim": (50.0700, 8.1900),
    "Schierstein": (50.0400, 8.1900),
    "Sonnenberg": (50.0950, 8.2800),
    "Rambach": (50.1150, 8.2900),
    "Naurod": (50.1300, 8.2700),
    "Auringen": (50.1250, 8.3000),
    "Medenbach": (50.1150, 8.3300),
    "Breckenheim": (50.0900, 8.3600),
    "Nordenstadt": (50.0600, 8.3300),
    "Delkenheim": (50.0450, 8.3400),
    "Erbenheim": (50.0550, 8.2900),
    "Bierstadt": (50.0800, 8.2800),
    "Kloppenheim": (50.1000, 8.3050),
    "Igstadt": (50.0900, 8.3200),
    "Heszloch": (50.1250, 8.2400),
    "Frauenstein": (50.0650, 8.1650),
    "Kohlheck": (50.0850, 8.1950),
    "Klarenthal": (50.0950, 8.2150),
    "Amoeneburg": (50.0250, 8.2700),
    "Mainz-Kastel": (50.0100, 8.2900),
    "Kastel": (50.0100, 8.2900),
    "Mainz-Kostheim": (50.0050, 8.3200),
    "Kostheim": (50.0050, 8.3200),
}


def normalise(text: str) -> str:
    """Lowercase, strip accents and umlauts so lookups are robust."""
    text = text.replace("ß", "ss")
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
    )
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


_NORMALISED_DISTRICTS = {normalise(name): name for name in DISTRICT_COORDS}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return round(2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a)), 3)


def detect_district(text: str) -> str:
    """Find a Wiesbaden district name inside free text (address, title, ...)."""
    haystack = normalise(text)
    # Longest names first so "Mainz-Kastel" wins over "Kastel".
    for key in sorted(_NORMALISED_DISTRICTS, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", haystack):
            return _NORMALISED_DISTRICTS[key]
    return ""


def coords_for_district(district: str) -> Optional[Tuple[float, float]]:
    return DISTRICT_COORDS.get(_NORMALISED_DISTRICTS.get(normalise(district), ""))


class Geocoder:
    """Cached, rate-limited geocoder with an offline district fallback."""

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        allow_network: bool = True,
        min_interval_seconds: float = 1.0,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self.allow_network = allow_network
        self.min_interval_seconds = min_interval_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request = 0.0
        self._cache: Dict[str, Optional[Tuple[float, float]]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self.cache_path and self.cache_path.exists():
            try:
                raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
                self._cache = {
                    key: (tuple(value) if value else None) for key, value in raw.items()
                }
            except (OSError, ValueError) as exc:
                LOGGER.warning("Could not read geocode cache: %s", exc)

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(
                    {key: list(value) if value else None for key, value in self._cache.items()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            LOGGER.warning("Could not write geocode cache: %s", exc)

    def geocode(self, address: str, district: str = "") -> Optional[Tuple[float, float]]:
        """Resolve an address to (lat, lon); ``None`` if nothing is known."""
        if district:
            local = coords_for_district(district)
            if local:
                return local

        detected = detect_district(address)
        if detected:
            local = coords_for_district(detected)
            if local:
                return local

        if not address.strip() or not self.allow_network:
            return None

        key = normalise(address)
        if key in self._cache:
            return self._cache[key]

        result = self._query_nominatim(address)
        self._cache[key] = result
        self._save_cache()
        return result

    def _query_nominatim(self, address: str) -> Optional[Tuple[float, float]]:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request = time.monotonic()

        try:
            response = requests.get(
                NOMINATIM_URL,
                params={"q": address, "format": "json", "limit": 1, "countrycodes": "de"},
                headers={"User-Agent": NOMINATIM_USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("Geocoding failed for %r: %s", address, exc)
            return None

        if not payload:
            return None
        try:
            return float(payload[0]["lat"]), float(payload[0]["lon"])
        except (KeyError, TypeError, ValueError):
            return None
