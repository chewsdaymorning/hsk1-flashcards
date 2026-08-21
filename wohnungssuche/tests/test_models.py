import unittest
from datetime import datetime

from wohnungssuche.models import AgentMessage, ApartmentListing, is_real_url
from tests.helpers import VALID_URL, make_listing


class TestUrlGuards(unittest.TestCase):
    def test_placeholder_urls_are_not_real(self):
        for url in (
            "https://example.com/listing/1",
            "https://picsum.photos/800/600",
            "/expose/123",
            "",
            "ftp://immobilienscout24.de/x",
        ):
            self.assertFalse(is_real_url(url), url)

    def test_platform_urls_are_real(self):
        self.assertTrue(is_real_url(VALID_URL))
        self.assertTrue(is_real_url("https://www.kleinanzeigen.de/s-anzeige/x/1-203-3600"))

    def test_fake_expose_url_is_rejected(self):
        with self.assertRaises(ValueError):
            make_listing(url="https://example.com/listing/123")

    def test_placeholder_images_are_dropped(self):
        listing = make_listing(
            image_urls=[
                "https://picsum.photos/800/600",
                "https://pictures.immobilienscout24.de/x/1.jpg",
            ]
        )
        self.assertEqual(
            listing.image_urls, ["https://pictures.immobilienscout24.de/x/1.jpg"]
        )


class TestDerivedValues(unittest.TestCase):
    def test_price_per_sqm(self):
        self.assertEqual(make_listing(warm_rent=1600, area_sqm=80).price_per_sqm, 20.0)

    def test_price_per_sqm_without_area(self):
        listing = make_listing()
        listing.area_sqm = 0
        self.assertIsNone(listing.price_per_sqm)

    def test_hash_is_stable_and_content_sensitive(self):
        first = make_listing()
        self.assertEqual(first.unique_hash, make_listing().unique_hash)
        self.assertNotEqual(first.unique_hash, make_listing(warm_rent=1401).unique_hash)

    def test_round_trip(self):
        original = make_listing(published_at=datetime(2026, 5, 1, 12, 0))
        restored = ApartmentListing.from_dict(original.to_dict())
        self.assertEqual(restored.unique_hash, original.unique_hash)
        self.assertEqual(restored.published_at, original.published_at)


class TestAgentMessage(unittest.TestCase):
    def test_ok_flag_and_listings(self):
        message = AgentMessage(sender="a", recipient="b", payload={"listings": [make_listing()]})
        self.assertTrue(message.ok)
        self.assertEqual(len(message.listings()), 1)
        self.assertFalse(AgentMessage(sender="a", recipient="b", errors=["boom"]).ok)


if __name__ == "__main__":
    unittest.main()
