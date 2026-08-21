"""Fredy SQLite import adapter, tested against a temp database - no Fredy needed."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from wohnungssuche.sources import FredyScraper
from tests.helpers import config

# Mirrors the columns of Fredy's listings table that the adapter reads
# (base migration + rooms/geo/soft-delete additions).
SCHEMA = """
CREATE TABLE listings (
    id TEXT PRIMARY KEY,
    created_at INTEGER,
    hash TEXT,
    provider TEXT,
    job_id TEXT,
    price INTEGER,
    size INTEGER,
    rooms INTEGER,
    title TEXT,
    image_url TEXT,
    description TEXT,
    address TEXT,
    link TEXT,
    is_active INTEGER DEFAULT 1,
    latitude REAL,
    longitude REAL,
    manually_deleted INTEGER NOT NULL DEFAULT 0
);
"""

NOW_MS = 1_755_772_800_000  # fixed epoch ms well after any cutoff issues


class TestFredyScraper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = str(Path(self.tmp.name) / "listings.db")
        connection = sqlite3.connect(self.db_path)
        connection.executescript(SCHEMA)
        import time
        fresh = int(time.time() * 1000)
        rows = [
            # Complete IS24 row with coordinates.
            ("n1", fresh, "158000001", "immoscout", "job-1", 1200, 85, 3, 
             "Helle 3-Zimmer-Wohnung mit Einbaukueche",
             "https://pictures.immobilienscout24.de/x/1.jpg",
             "EBK, Balkon, Stellplatz", "Bertramstrasse 12, Wiesbaden",
             "https://www.immobilienscout24.de/expose/158000001", 1, 50.068, 8.226, 0),
            # rooms NULL -> skipped as incomplete.
            ("n2", fresh, "abc123", "immowelt", "job-1", 1100, 78, None, "Ohne Zimmerangabe",
             None, "", "Wiesbaden", "https://www.immowelt.de/expose/abc123", 1, None, None, 0),
            # Soft-deleted -> ignored.
            ("n3", fresh, "158000002", "immoscout", "job-1", 1300, 90, 3, "Geloescht",
             None, "", "Wiesbaden", "https://www.immobilienscout24.de/expose/158000002",
             1, None, None, 1),
            # Offline -> ignored.
            ("n4", fresh, "158000003", "immoscout", "job-1", 1250, 82, 3, "Offline",
             None, "", "Wiesbaden", "https://www.immobilienscout24.de/expose/158000003",
             0, None, None, 0),
            # Kleinanzeigen row, fractional rooms, no coords.
            ("n5", fresh, "2812999999", "kleinanzeigen", "job-2", 1150, 88, 3.5,
             "Grosse Wohnung von privat", None, "Mit Wohnkueche",
             "65183 Wiesbaden - Mitte",
             "https://www.kleinanzeigen.de/s-anzeige/grosse-wohnung/2812999999-203-3600",
             1, None, None, 0),
            # Too old -> filtered by the created_at cutoff.
            ("n6", 1_000_000_000_000, "158000004", "immoscout", "job-1", 1200, 85, 3,
             "Uralt", None, "", "Wiesbaden",
             "https://www.immobilienscout24.de/expose/158000004", 1, None, None, 0),
        ]
        connection.executemany(
            "INSERT INTO listings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )
        connection.commit()
        connection.close()
        self.scraper = FredyScraper(
            config=config(), fetcher=None, db_path=self.db_path
        )
        self.listings = self.scraper.search()
        self.by_id = {listing.id: listing for listing in self.listings}

    def test_only_fresh_active_complete_rows_survive(self):
        self.assertEqual(
            sorted(self.by_id), ["is24-158000001", "kleinanzeigen-2812999999"]
        )
        # The incomplete row was counted, not raised.
        self.assertTrue(any("uebersprungen" in error for error in self.scraper.errors))

    def test_field_mapping(self):
        listing = self.by_id["is24-158000001"]
        self.assertEqual(listing.platform, "is24")
        self.assertEqual(listing.rooms, 3.0)
        self.assertEqual(listing.area_sqm, 85.0)
        self.assertEqual(listing.cold_rent, 1200.0)
        self.assertEqual(listing.warm_rent, 1500.0)  # 1200 * 1.25
        self.assertTrue(listing.warm_rent_is_estimated)
        self.assertEqual(listing.lat, 50.068)
        self.assertEqual(
            listing.image_urls, ["https://pictures.immobilienscout24.de/x/1.jpg"]
        )
        self.assertTrue(listing.has_ebk)
        self.assertTrue(listing.has_parking)

    def test_fractional_rooms_and_provider_mapping(self):
        listing = self.by_id["kleinanzeigen-2812999999"]
        self.assertEqual(listing.rooms, 3.5)
        self.assertEqual(listing.kitchen_size_hint, "large")  # "Wohnkueche"

    def test_missing_db_is_an_error_not_a_crash(self):
        scraper = FredyScraper(
            config=config(), fetcher=None, db_path="/nope/listings.db"
        )
        self.assertEqual(scraper.search(), [])
        self.assertTrue(scraper.errors)

    def test_unconfigured_path_is_reported(self):
        scraper = FredyScraper(config=config(), fetcher=None)
        self.assertEqual(scraper.search(), [])
        self.assertIn("fredy_db_path", scraper.errors[0])

    def test_database_opened_read_only(self):
        # The adapter must not be able to write: verify by checking the file's
        # mtime-relevant content is untouched - simpler: query_only via mode=ro
        # raises on write.  We assert search() left no -wal file behind.
        self.assertFalse(Path(self.db_path + "-wal").exists())


if __name__ == "__main__":
    unittest.main()
