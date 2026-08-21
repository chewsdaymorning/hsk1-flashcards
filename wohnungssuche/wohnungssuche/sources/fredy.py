"""Import listings found by Fredy (github.com/orangecoding/fredy).

Fredy is a Node.js real-estate watcher that already solves the hard discovery
problem (including ImmoScout24, via their mobile API).  It persists everything
it finds in a WAL-mode SQLite file - by default ``<fredy>/db/listings.db`` -
whose ``listings`` table stores price/size/rooms as numbers and the absolute
listing URL in ``link``.  WAL explicitly supports a concurrent reader next to
Fredy's single writer, so this adapter opens the file strictly read-only and
never blocks Fredy.

This is discovery only: rows become ApartmentListing objects and run through
the same validation -> filter -> report pipeline as scraped results.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from wohnungssuche.models import ApartmentListing, RawListing, is_real_url
from wohnungssuche.parsing import clean_text, detect_features, kitchen_size_hint
from wohnungssuche.scrapers.base import BaseScraper
from wohnungssuche.scrapers.card import WARM_RENT_ESTIMATE_FACTOR

# Fredy provider ids -> our platform names.  Unknown providers keep their
# Fredy name so the report still shows where a listing came from.
PROVIDER_MAP = {
    "immoscout": "is24",
    "immoscout24": "is24",
    "immowelt": "immowelt",
    "kleinanzeigen": "kleinanzeigen",
    "ebayKleinanzeigen": "kleinanzeigen",
}


@dataclass
class FredyScraper(BaseScraper):
    """Reads Fredy's listings.db; ``fetcher`` is unused (no network here)."""

    platform: str = "fredy"
    db_path: str = ""  # empty -> config.fredy_db_path
    since_days: int = 3

    def _resolved_db_path(self) -> str:
        return self.db_path or self.config.fredy_db_path

    # --- Discovery --------------------------------------------------------
    def discover(self) -> List[RawListing]:
        path = self._resolved_db_path()
        if not path:
            self.log_error(
                "fredy_db_path ist nicht gesetzt (Pfad zu Fredys listings.db)"
            )
            return []

        cutoff_ms = int(
            (datetime.now() - timedelta(days=self.since_days)).timestamp() * 1000
        )
        try:
            # mode=ro: never write, never create; WAL allows this while Fredy
            # runs.  busy_timeout rides out transient writer locks.
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
            try:
                connection.execute("PRAGMA busy_timeout = 5000")
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM listings WHERE created_at > ? ORDER BY created_at",
                    (cutoff_ms,),
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            self.log_error(f"Fredy-Datenbank {path} nicht lesbar: {exc}")
            return []

        payload = json.dumps([dict(row) for row in rows], ensure_ascii=False)
        return [
            RawListing(platform=self.platform, source_url=f"sqlite:{path}", html=payload)
        ]

    # --- Extraction -------------------------------------------------------
    def extract(self, raw: RawListing) -> List[ApartmentListing]:
        try:
            rows: List[Dict[str, Any]] = json.loads(raw.html)
        except ValueError as exc:
            self.log_error(f"Fredy-Datenexport unlesbar: {exc}")
            return []

        listings: List[ApartmentListing] = []
        skipped_incomplete = 0
        for row in rows:
            # Soft-deleted or offline rows are Fredy's business, not ours.
            if row.get("manually_deleted"):
                continue
            if row.get("is_active") == 0:
                continue
            listing = self._map_row(row)
            if listing is None:
                skipped_incomplete += 1
            else:
                listings.append(listing)
        if skipped_incomplete:
            self.log_error(
                f"{skipped_incomplete} Fredy-Treffer ohne Zimmer/Flaeche/Preis "
                "oder mit unbrauchbarem Link uebersprungen"
            )
        return listings

    def _map_row(self, row: Dict[str, Any]) -> Optional[ApartmentListing]:
        url = (row.get("link") or "").strip()
        rooms = _as_float(row.get("rooms"))
        area = _as_float(row.get("size"))
        price = _as_float(row.get("price"))
        if not is_real_url(url) or rooms is None or area is None or price is None:
            return None

        provider = str(row.get("provider") or "fredy")
        platform = PROVIDER_MAP.get(provider, provider)
        listing_id = str(row.get("hash") or row.get("id") or url.rsplit("/", 1)[-1])

        title = clean_text(str(row.get("title") or f"Wohnung {listing_id}"))
        description = clean_text(str(row.get("description") or ""))
        address = clean_text(str(row.get("address") or ""))
        image_url = (row.get("image_url") or "").strip()

        # Fredy stores one price per listing; for rentals that is almost
        # always the Kaltmiete, so the warm rent stays an estimate here and is
        # labelled as such everywhere downstream.
        warm_rent = round(price * WARM_RENT_ESTIMATE_FACTOR, 2)

        haystack = f"{title} {description}"
        published_at = None
        created_ms = row.get("created_at")
        if isinstance(created_ms, (int, float)) and created_ms > 0:
            published_at = datetime.fromtimestamp(created_ms / 1000)

        try:
            return ApartmentListing(
                id=f"{platform}-{listing_id}",
                platform=platform,
                url=url,
                title=title,
                description=description,
                address=address,
                rooms=rooms,
                area_sqm=area,
                cold_rent=price,
                warm_rent=warm_rent,
                warm_rent_is_estimated=True,
                lat=_as_float(row.get("latitude")),
                lon=_as_float(row.get("longitude")),
                image_urls=[image_url] if image_url else [],
                kitchen_size_hint=kitchen_size_hint(
                    haystack, self.config.small_kitchen_terms
                ),
                published_at=published_at,
                **detect_features(haystack),
            )
        except ValueError:
            return None  # placeholder-host URL slipped through is_real_url? guard anyway


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
