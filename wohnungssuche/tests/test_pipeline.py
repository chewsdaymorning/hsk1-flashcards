"""End-to-end pipeline tests, fixtures only - no network is touched."""

import json
import tempfile
import unittest
from pathlib import Path

from wohnungssuche.agents import Orchestrator
from wohnungssuche.agents.orchestrator import build_scrapers
from wohnungssuche.models import ApprovalStatus
from wohnungssuche.scrapers.base import BaseScraper
from wohnungssuche.storage import Storage
from tests.helpers import config


class ExplodingScraper(BaseScraper):
    """A platform that is down: every call raises."""

    def discover(self):
        raise RuntimeError("platform down")

    def extract(self, raw):
        raise RuntimeError("platform down")


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / "reports"
        self.storage = Storage(Path(self.tmp.name) / "test.db")
        self.config = config(fetch_details=False)
        self.orchestrator = Orchestrator(
            config=self.config,
            storage=self.storage,
            output_dir=self.output,
            use_mock=True,
        )
        self.result = self.orchestrator.run()

    def tearDown(self):
        self.storage.close()
        self.tmp.cleanup()

    def test_run_completes_without_errors(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual(len(self.result.agent_log), 6)
        self.assertTrue(all(not entry["errors"] for entry in self.result.agent_log))

    def test_all_platforms_contributed(self):
        found = {status.platform: status.listings_found for status in self.result.platform_status}
        self.assertEqual(found, {"is24": 6, "immowelt": 3, "kleinanzeigen": 3})

    def test_matches_satisfy_every_criterion(self):
        self.assertTrue(self.result.matches)
        for listing in self.result.matches:
            self.assertGreaterEqual(listing.rooms, self.config.min_rooms)
            self.assertGreaterEqual(listing.area_sqm, self.config.min_area_sqm)
            self.assertLessEqual(listing.warm_rent, self.config.max_warm_rent_eur)
            self.assertLessEqual(
                listing.distance_to_center_km, self.config.max_distance_km
            )
            self.assertNotIn(listing.district, self.config.excluded_districts)
            self.assertFalse(listing.is_scam_flagged)

    def test_excluded_listings_carry_a_reason(self):
        for listing in self.result.non_matches:
            self.assertTrue(listing.exclude_reasons, listing.id)

    def test_scam_listing_is_flagged_and_excluded(self):
        flagged_ids = {listing.id for listing in self.result.flagged}
        self.assertIn("kleinanzeigen-2812345679", flagged_ids)
        self.assertNotIn(
            "kleinanzeigen-2812345679", {listing.id for listing in self.result.matches}
        )

    def test_enrichment_adds_district_and_distance(self):
        for listing in self.result.matches:
            self.assertTrue(listing.district)
            self.assertIsNotNone(listing.distance_to_center_km)

    def test_report_contains_real_links_only(self):
        html = Path(self.result.report_path).read_text(encoding="utf-8")
        self.assertNotIn("example.com", html)
        self.assertNotIn("picsum", html)
        for listing in self.result.matches:
            self.assertIn(listing.url, html)

    def test_json_snapshot_matches_result(self):
        payload = json.loads(Path(self.result.json_path).read_text(encoding="utf-8"))
        self.assertEqual(len(payload["matches"]), len(self.result.matches))

    def test_listings_are_persisted_and_deduplicated(self):
        self.assertEqual(len(self.result.new_hashes), self.result.total_found)
        second = Orchestrator(
            config=self.config,
            storage=self.storage,
            output_dir=self.output,
            use_mock=True,
        ).run()
        self.assertEqual(second.new_hashes, set())
        self.assertEqual(len(second.matches), len(self.result.matches))

    def test_matches_are_queued_as_pending_only(self):
        pending = self.storage.approvals(ApprovalStatus.PENDING)
        self.assertEqual(len(pending), len(self.result.matches))
        self.assertEqual(self.storage.approvals(ApprovalStatus.APPROVED), [])

    def test_run_is_recorded(self):
        runs = self.storage.recent_runs()
        self.assertEqual(runs[0]["matches"], len(self.result.matches))
        self.assertEqual(runs[0]["report_path"], self.result.report_path)


class TestPartialFailure(unittest.TestCase):
    def test_one_broken_platform_does_not_stop_the_run(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        search_config = config(fetch_details=False, platforms=["is24"])
        scrapers = build_scrapers(search_config, use_mock=True)
        scrapers["kaputt"] = ExplodingScraper(config=search_config, fetcher=None)

        orchestrator = Orchestrator(
            config=search_config,
            storage=None,
            scrapers=scrapers,
            output_dir=Path(tmp.name),
            use_mock=True,
        )
        result = orchestrator.run()

        statuses = {status.platform: status.success for status in result.platform_status}
        self.assertTrue(statuses["is24"])
        self.assertFalse(statuses["kaputt"])
        self.assertTrue(result.matches)  # the healthy platform still delivered
        self.assertTrue(Path(result.report_path).exists())


class TestNoAutomaticContact(unittest.TestCase):
    def test_package_contains_no_sending_code(self):
        """A crude but effective guard: nothing may send mail or submit forms."""
        package = Path(__file__).resolve().parent.parent / "wohnungssuche"
        forbidden = ("smtplib", "sendmail", "requests.post", "session.post", "yagmail")
        offenders = []
        for path in package.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            offenders.extend(
                f"{path.name}: {needle}" for needle in forbidden if needle in text
            )
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
