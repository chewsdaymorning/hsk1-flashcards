"""SQLite persistence: seen listings, run history and the approval queue.

The approval queue is the only place where "contacting a landlord" is tracked,
and it is deliberately inert: this package never sends anything.  Approving a
listing merely records that the user wants to write to it themselves.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from wohnungssuche.models import ApartmentListing, ApprovalStatus, PlatformStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    unique_hash      TEXT PRIMARY KEY,
    listing_id       TEXT NOT NULL,
    platform         TEXT NOT NULL,
    url              TEXT NOT NULL,
    title            TEXT NOT NULL,
    warm_rent        REAL,
    rooms            REAL,
    area_sqm         REAL,
    matches_criteria INTEGER NOT NULL DEFAULT 0,
    is_scam_flagged  INTEGER NOT NULL DEFAULT 0,
    payload          TEXT NOT NULL,
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    unique_hash  TEXT PRIMARY KEY,
    listing_id   TEXT NOT NULL,
    status       TEXT NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    requested_at TEXT NOT NULL,
    decided_at   TEXT,
    FOREIGN KEY (unique_hash) REFERENCES listings (unique_hash)
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT NOT NULL,
    found        INTEGER NOT NULL DEFAULT 0,
    new_listings INTEGER NOT NULL DEFAULT 0,
    matches      INTEGER NOT NULL DEFAULT 0,
    scam_flagged INTEGER NOT NULL DEFAULT 0,
    platforms    TEXT NOT NULL DEFAULT '[]',
    report_path  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings (last_seen_at);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status);
"""


class Storage:
    """Thin SQLite wrapper; safe to construct repeatedly."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    # --- lifecycle --------------------------------------------------------
    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- listings ---------------------------------------------------------
    def upsert_listing(self, listing: ApartmentListing) -> bool:
        """Insert or refresh a listing.  Returns True if it is new."""
        now = datetime.now().isoformat()
        payload = json.dumps(listing.to_dict(), ensure_ascii=False)
        cursor = self.connection.execute(
            "SELECT first_seen_at FROM listings WHERE unique_hash = ?",
            (listing.unique_hash,),
        )
        row = cursor.fetchone()
        is_new = row is None
        self.connection.execute(
            """
            INSERT INTO listings (unique_hash, listing_id, platform, url, title,
                                  warm_rent, rooms, area_sqm, matches_criteria,
                                  is_scam_flagged, payload, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (unique_hash) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                matches_criteria = excluded.matches_criteria,
                is_scam_flagged = excluded.is_scam_flagged,
                payload = excluded.payload
            """,
            (
                listing.unique_hash,
                listing.id,
                listing.platform,
                listing.url,
                listing.title,
                listing.warm_rent,
                listing.rooms,
                listing.area_sqm,
                int(listing.matches_criteria),
                int(listing.is_scam_flagged),
                payload,
                row["first_seen_at"] if row else now,
                now,
            ),
        )
        self.connection.commit()
        return is_new

    def save_listings(self, listings: Iterable[ApartmentListing]) -> List[str]:
        """Store many listings, returning the hashes that were new."""
        return [
            listing.unique_hash for listing in listings if self.upsert_listing(listing)
        ]

    def known_hashes(self) -> set:
        return {
            row["unique_hash"]
            for row in self.connection.execute("SELECT unique_hash FROM listings")
        }

    def get_listing(self, unique_hash: str) -> Optional[ApartmentListing]:
        row = self.connection.execute(
            "SELECT payload FROM listings WHERE unique_hash = ?", (unique_hash,)
        ).fetchone()
        return ApartmentListing.from_dict(json.loads(row["payload"])) if row else None

    # --- approval queue ---------------------------------------------------
    def request_approval(self, listing: ApartmentListing, note: str = "") -> None:
        """Put a listing in front of the user.  Never contacts anyone."""
        self.connection.execute(
            """
            INSERT INTO approvals (unique_hash, listing_id, status, note, requested_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (unique_hash) DO NOTHING
            """,
            (
                listing.unique_hash,
                listing.id,
                ApprovalStatus.PENDING.value,
                note,
                datetime.now().isoformat(),
            ),
        )
        self.connection.commit()

    def set_approval(
        self, unique_hash: str, status: ApprovalStatus, note: str = ""
    ) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE approvals
               SET status = ?, decided_at = ?, note = CASE WHEN ? = '' THEN note ELSE ? END
             WHERE unique_hash = ?
            """,
            (status.value, datetime.now().isoformat(), note, note, unique_hash),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def approvals(
        self, status: Optional[ApprovalStatus] = None
    ) -> List[Tuple[Dict, ApartmentListing]]:
        query = """
            SELECT a.unique_hash, a.status, a.note, a.requested_at, a.decided_at, l.payload
              FROM approvals a
              JOIN listings l ON l.unique_hash = a.unique_hash
        """
        params: Sequence = ()
        if status:
            query += " WHERE a.status = ?"
            params = (status.value,)
        query += " ORDER BY a.requested_at DESC"
        results = []
        for row in self.connection.execute(query, params):
            entry = {
                "unique_hash": row["unique_hash"],
                "status": row["status"],
                "note": row["note"],
                "requested_at": row["requested_at"],
                "decided_at": row["decided_at"],
            }
            results.append((entry, ApartmentListing.from_dict(json.loads(row["payload"]))))
        return results

    # --- runs -------------------------------------------------------------
    def record_run(
        self,
        started_at: datetime,
        finished_at: datetime,
        found: int,
        new_listings: int,
        matches: int,
        scam_flagged: int,
        platforms: Sequence[PlatformStatus],
        report_path: str = "",
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO runs (started_at, finished_at, found, new_listings, matches,
                              scam_flagged, platforms, report_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at.isoformat(),
                finished_at.isoformat(),
                found,
                new_listings,
                matches,
                scam_flagged,
                json.dumps([status.__dict__ for status in platforms], ensure_ascii=False),
                report_path,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def recent_runs(self, limit: int = 10) -> List[Dict]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


@contextmanager
def open_storage(path: str | Path):
    storage = Storage(path)
    try:
        yield storage
    finally:
        storage.close()
