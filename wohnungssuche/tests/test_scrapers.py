import unittest
from pathlib import Path

from wohnungssuche.scrapers import (
    FixtureFetcher,
    ImmoweltScraper,
    IS24Scraper,
    KleinanzeigenScraper,
    MockScraper,
    RobotsPolicy,
)
from wohnungssuche.scrapers.base import FetchResult
from tests.helpers import config

FIXTURES = Path(__file__).resolve().parent.parent / "wohnungssuche" / "fixtures"


class TestFixtureFetcher(unittest.TestCase):
    def test_serves_pages_then_empties(self):
        fetcher = FixtureFetcher({"is24": FIXTURES / "is24_results.html"})
        first = fetcher.get("https://is24.example/search")
        second = fetcher.get("https://is24.example/search")
        self.assertTrue(first.ok)
        self.assertIn("result-list", first.html)
        self.assertTrue(second.ok)
        self.assertNotIn("result-list__listing", second.html)

    def test_unknown_url(self):
        result = FixtureFetcher({}).get("https://elsewhere.test/")
        self.assertFalse(result.ok)


class TestIS24Parsing(unittest.TestCase):
    def setUp(self):
        self.scraper = MockScraper(config=config(), fetcher=None, platform="is24")
        self.listings = self.scraper.search()
        self.by_id = {listing.id: listing for listing in self.listings}

    def test_finds_every_card(self):
        self.assertEqual(len(self.listings), 6)
        self.assertEqual(self.scraper.errors, [])

    def test_urls_are_real_and_absolute(self):
        for listing in self.listings:
            self.assertTrue(
                listing.url.startswith("https://www.immobilienscout24.de/expose/"),
                listing.url,
            )

    def test_images_come_from_the_platform_cdn(self):
        listing = self.by_id["is24-150000001"]
        self.assertTrue(listing.image_urls)
        self.assertTrue(listing.image_urls[0].startswith("https://pictures.immobilienscout24.de/"))
        # The inline base64 tracking pixel must not be picked up.
        self.assertFalse(any(url.startswith("data:") for url in listing.image_urls))

    def test_core_figures(self):
        listing = self.by_id["is24-150000001"]
        self.assertEqual(listing.rooms, 3.0)
        self.assertEqual(listing.area_sqm, 86.0)
        self.assertEqual(listing.warm_rent, 1420.0)
        self.assertEqual(listing.cold_rent, 1150.0)
        self.assertFalse(listing.warm_rent_is_estimated)
        self.assertIn("Rheingauviertel", listing.address)
        self.assertTrue(listing.has_parking)

    def test_decimal_rooms(self):
        self.assertEqual(self.by_id["is24-150000002"].rooms, 3.5)

    def test_warm_rent_is_estimated_when_only_cold_rent_published(self):
        listing = self.by_id["is24-150000006"]
        self.assertTrue(listing.warm_rent_is_estimated)
        self.assertAlmostEqual(listing.warm_rent, 1150.0 * 1.25, places=2)

    def test_small_kitchen_hint(self):
        self.assertEqual(self.by_id["is24-150000005"].kitchen_size_hint, "small")


class TestOtherPlatforms(unittest.TestCase):
    def test_immowelt(self):
        listings = MockScraper(config=config(), fetcher=None, platform="immowelt").search()
        self.assertEqual(len(listings), 3)
        first = listings[0]
        self.assertEqual(first.url, "https://www.immowelt.de/expose/2xk4m5q")
        self.assertEqual(first.rooms, 3.0)
        self.assertEqual(first.area_sqm, 84.0)
        self.assertEqual(first.cold_rent, 1240.0)
        self.assertEqual(first.nebenkosten, 250.0)
        self.assertEqual(first.warm_rent, 1490.0)
        self.assertEqual(first.deposit, 3720.0)
        self.assertTrue(first.image_urls[0].startswith("https://ces.immowelt.org/"))

    def test_kleinanzeigen(self):
        listings = MockScraper(
            config=config(), fetcher=None, platform="kleinanzeigen"
        ).search()
        self.assertEqual(len(listings), 3)
        first = listings[0]
        self.assertTrue(first.url.startswith("https://www.kleinanzeigen.de/s-anzeige/"))
        self.assertEqual(first.id, "kleinanzeigen-2812345678")
        self.assertEqual(first.rooms, 3.0)
        self.assertEqual(first.area_sqm, 82.0)

    def test_unknown_platform_rejected(self):
        with self.assertRaises(ValueError):
            MockScraper(config=config(), fetcher=None, platform="wggesucht")


class TestSearchParameters(unittest.TestCase):
    def test_is24_params_reflect_criteria(self):
        scraper = IS24Scraper(config=config(), fetcher=FixtureFetcher({}))
        params = scraper.search_params(2)
        self.assertEqual(params["numberofrooms"], "3.0-")
        self.assertEqual(params["livingspace"], "70.0-")
        self.assertEqual(params["price"], "-1600.0")
        self.assertEqual(params["pagenumber"], "2")

    def test_immowelt_and_kleinanzeigen_urls(self):
        immowelt = ImmoweltScraper(config=config(), fetcher=FixtureFetcher({}))
        self.assertEqual(
            immowelt.search_url(), "https://www.immowelt.de/liste/wiesbaden/wohnungen/mieten"
        )
        kleinanzeigen = KleinanzeigenScraper(config=config(), fetcher=FixtureFetcher({}))
        self.assertIn("wohnung-mieten/wiesbaden", kleinanzeigen.search_url())


class TestDiscoveryResilience(unittest.TestCase):
    class BrokenFetcher:
        def get(self, url, params=None):
            return FetchResult(url=url, ok=False, error="HTTP 403")

    def test_failed_fetch_is_recorded_not_raised(self):
        scraper = IS24Scraper(config=config(), fetcher=self.BrokenFetcher())
        self.assertEqual(scraper.discover(), [])
        self.assertTrue(scraper.errors)
        self.assertIn("403", scraper.errors[0])

    def test_pagination_stops_on_empty_page(self):
        scraper = MockScraper(
            config=config(max_pages_per_platform=5), fetcher=None, platform="is24"
        )
        pages = scraper.discover()
        # First page has results, second comes back empty and ends the loop.
        self.assertEqual(len(pages), 2)


class TestHttpFetcherVerify(unittest.TestCase):
    """Status-code mapping of the liveness check, no network involved."""

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def close(self):
            pass

    def build_fetcher(self, status_code):
        from wohnungssuche.scrapers.base import HttpFetcher

        fetcher = HttpFetcher.__new__(HttpFetcher)  # skip network-y __init__
        fetcher.config = config(respect_robots_txt=False, request_delay_seconds=0)
        fetcher._last_request_at = 0.0

        outer = self

        class FakeSession:
            def head(self, url, timeout=None, allow_redirects=True):
                return outer.FakeResponse(status_code)

            def get(self, url, timeout=None, stream=False):  # 405 fallback
                return outer.FakeResponse(200)

        fetcher.session = FakeSession()
        fetcher.robots = None  # unused with respect_robots_txt=False
        return fetcher

    def test_mapping(self):
        cases = {200: True, 301: True, 404: False, 410: False,
                 403: None, 429: None, 500: None}
        for status, expected in cases.items():
            fetcher = self.build_fetcher(status)
            self.assertEqual(
                fetcher.verify("https://www.immobilienscout24.de/expose/1"),
                expected,
                f"HTTP {status}",
            )

    def test_head_not_allowed_falls_back_to_get(self):
        fetcher = self.build_fetcher(405)
        self.assertTrue(fetcher.verify("https://www.immowelt.de/expose/x"))


class TestRobotsPolicy(unittest.TestCase):
    def test_unreachable_robots_means_no_crawling(self):
        policy = RobotsPolicy("test-agent")
        policy._cache["https://blocked.test"] = None
        self.assertFalse(policy.can_fetch("https://blocked.test/Suche"))

    def test_rules_are_honoured(self):
        from urllib.robotparser import RobotFileParser

        parser = RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /Suche/"])
        policy = RobotsPolicy("test-agent")
        policy._cache["https://allowed.test"] = parser
        self.assertFalse(policy.can_fetch("https://allowed.test/Suche/de"))
        self.assertTrue(policy.can_fetch("https://allowed.test/expose/1"))


if __name__ == "__main__":
    unittest.main()
