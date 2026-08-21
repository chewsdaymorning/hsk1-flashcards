import tempfile
import unittest
from datetime import date
from pathlib import Path

from wohnungssuche.sources import EmailAlertScraper, FileMailbox
from wohnungssuche.sources.mailbox import imap_since_criterion, portal_expose_url
from tests.helpers import config

EMAIL_FIXTURES = (
    Path(__file__).resolve().parent.parent / "wohnungssuche" / "fixtures" / "emails"
)


def email_scraper(mailbox=None) -> EmailAlertScraper:
    if mailbox is None:
        mailbox = FileMailbox(EMAIL_FIXTURES)
    return EmailAlertScraper(config=config(), fetcher=None, mailbox=mailbox)


class TestFileMailbox(unittest.TestCase):
    def test_returns_every_fixture(self):
        messages = FileMailbox(EMAIL_FIXTURES).fetch()
        self.assertEqual(len(messages), 2)
        for raw in messages:
            self.assertIsInstance(raw, bytes)
            self.assertIn(b"X-Demo: synthetic fixture", raw)


class TestDiscover(unittest.TestCase):
    def test_one_raw_listing_per_email(self):
        scraper = email_scraper()
        raws = scraper.discover()
        self.assertEqual(len(raws), 2)
        self.assertEqual(scraper.errors, [])
        for raw in raws:
            self.assertEqual(raw.platform, "email")
            self.assertTrue(raw.html.strip())
            self.assertIn("@", raw.source_url)  # the Message-ID header

    def test_missing_mailbox_logs_and_returns_nothing(self):
        scraper = EmailAlertScraper(config=config(), fetcher=None, mailbox=None)
        self.assertEqual(scraper.discover(), [])
        self.assertEqual(len(scraper.errors), 1)

    def test_broken_email_is_skipped_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "broken.eml").write_bytes(b"")
            scraper = email_scraper(mailbox=FileMailbox(Path(tmp)))
            self.assertEqual(scraper.discover(), [])
            self.assertEqual(len(scraper.errors), 1)


class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.scraper = email_scraper()
        self.listings = self.scraper.search()
        self.by_id = {listing.id: listing for listing in self.listings}

    def test_search_finds_every_listing(self):
        self.assertEqual(len(self.listings), 3)
        self.assertEqual(self.scraper.errors, [])
        hashes = {listing.unique_hash for listing in self.listings}
        self.assertEqual(len(hashes), 3)

    def test_is24_estimated_warm_rent(self):
        listing = self.by_id["is24-160000101"]
        self.assertEqual(listing.platform, "is24")
        self.assertEqual(listing.rooms, 3.0)
        self.assertEqual(listing.area_sqm, 84.0)
        self.assertEqual(listing.cold_rent, 1390.0)
        self.assertAlmostEqual(listing.warm_rent, 1390.0 * 1.25, places=2)
        self.assertTrue(listing.warm_rent_is_estimated)
        self.assertTrue(listing.has_balcony)
        # Tracking parameters must not survive into the expose URL.
        self.assertEqual(
            listing.url, "https://www.immobilienscout24.de/expose/160000101"
        )

    def test_is24_redirect_wrapper_is_unwrapped(self):
        listing = self.by_id["is24-160000102"]
        self.assertEqual(
            listing.url, "https://www.immobilienscout24.de/expose/160000102"
        )
        self.assertEqual(listing.rooms, 4.0)
        self.assertEqual(listing.area_sqm, 102.0)
        self.assertEqual(listing.cold_rent, 1550.0)
        self.assertEqual(listing.warm_rent, 1890.0)
        self.assertFalse(listing.warm_rent_is_estimated)
        self.assertEqual(
            listing.title, "Großzügige 4-Zimmer-Wohnung mit Einbauküche"
        )

    def test_immowelt_labeled_warm_rent(self):
        listing = self.by_id["immowelt-2ab34cd"]
        self.assertEqual(listing.platform, "immowelt")
        self.assertEqual(listing.url, "https://www.immowelt.de/expose/2ab34cd")
        self.assertEqual(listing.rooms, 3.0)
        self.assertEqual(listing.area_sqm, 78.0)
        self.assertEqual(listing.warm_rent, 1450.0)
        self.assertIsNone(listing.cold_rent)
        self.assertFalse(listing.warm_rent_is_estimated)


class TestUrlHelpers(unittest.TestCase):
    def test_kleinanzeigen_id_from_slug_path(self):
        resolved = portal_expose_url(
            "https://www.kleinanzeigen.de/s-anzeige/helle-3-zimmer-wohnung/2812345678-203-4892?utm_source=email"
        )
        self.assertEqual(
            resolved,
            (
                "kleinanzeigen",
                "https://www.kleinanzeigen.de/s-anzeige/helle-3-zimmer-wohnung/2812345678-203-4892",
                "2812345678",
            ),
        )

    def test_non_portal_links_are_ignored(self):
        self.assertIsNone(portal_expose_url("https://www.immobilienscout24.de/meinkonto"))
        self.assertIsNone(portal_expose_url("https://example.com/expose/123"))
        self.assertIsNone(portal_expose_url(""))


class TestImapSinceCriterion(unittest.TestCase):
    def test_formats_imap_date(self):
        self.assertEqual(
            imap_since_criterion(3, today=date(2026, 1, 4)), "01-Jan-2026"
        )

    def test_zero_days_is_today(self):
        self.assertEqual(
            imap_since_criterion(0, today=date(2026, 8, 21)), "21-Aug-2026"
        )


if __name__ == "__main__":
    unittest.main()
