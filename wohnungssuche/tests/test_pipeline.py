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
        self.assertEqual(len(self.result.agent_log), 7)
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


class TestDemoModeIsLabelled(unittest.TestCase):
    """A --mock report must say loudly that its links are synthetic."""

    def test_mock_report_carries_demo_banner_and_flag(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        result = Orchestrator(
            config=config(fetch_details=False),
            storage=None,
            output_dir=Path(tmp.name),
            use_mock=True,
        ).run()
        html = Path(result.report_path).read_text(encoding="utf-8")
        self.assertIn("Demo-Daten", html)
        self.assertIn("nicht existierenden Inseraten", html)
        payload = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
        self.assertTrue(payload["demo"])
        # No link checker runs in demo mode, so nothing may claim "ok".
        for listing in result.matches:
            self.assertEqual(listing.link_status, "unchecked")

    def test_live_report_has_no_demo_banner(self):
        from wohnungssuche.reporting import ReportGenerator
        from tests.helpers import make_listing

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        generator = ReportGenerator(config(), Path(tmp.name))
        html_path, json_path = generator.generate(
            matches=[make_listing()], non_matches=[], flagged=[], demo_mode=False
        )
        self.assertNotIn("Demo-Daten", html_path.read_text(encoding="utf-8"))
        self.assertFalse(json.loads(json_path.read_text(encoding="utf-8"))["demo"])


class TestLinkCheckAgent(unittest.TestCase):
    class StubFetcher:
        """verify() answers from a fixed table; get() is never used here."""

        def __init__(self, verdicts):
            self.verdicts = verdicts
            self.checked = []

        def get(self, url, params=None):  # pragma: no cover - not used
            raise AssertionError("LinkCheckAgent must not GET")

        def verify(self, url):
            self.checked.append(url)
            return self.verdicts.get(url)

    def run_agent(self, matches, fetcher, **config_overrides):
        from wohnungssuche.agents import LinkCheckAgent
        from wohnungssuche.models import AgentMessage

        agent = LinkCheckAgent(config=config(**config_overrides), fetcher=fetcher)
        message = AgentMessage(
            sender="FilterAgent",
            recipient="LinkCheckAgent",
            payload={"matches": matches, "warnings": {}},
        )
        return agent.run(message)

    def test_statuses_and_dead_warning(self):
        from tests.helpers import make_listing

        alive = make_listing(id="alive")
        gone = make_listing(id="gone", title="Andere Wohnung")
        unknown = make_listing(id="unknown", title="Dritte Wohnung")
        fetcher = self.StubFetcher(
            {alive.url: True, gone.url: False, unknown.url: None}
        )
        # Same URL for all three (helpers share one) would collide; give each its own.
        gone.url = "https://www.immobilienscout24.de/expose/222"
        unknown.url = "https://www.immobilienscout24.de/expose/333"
        fetcher.verdicts = {alive.url: True, gone.url: False, unknown.url: None}

        message = self.run_agent([alive, gone, unknown], fetcher)
        self.assertTrue(message.ok)
        self.assertEqual(alive.link_status, "ok")
        self.assertEqual(gone.link_status, "dead")
        self.assertEqual(unknown.link_status, "unchecked")
        self.assertIn(
            "Inserat nicht mehr erreichbar (evtl. schon vergeben)",
            message.payload["warnings"][gone.unique_hash],
        )

    def test_disabled_or_missing_fetcher_checks_nothing(self):
        from tests.helpers import make_listing

        listing = make_listing()
        fetcher = self.StubFetcher({listing.url: False})
        self.run_agent([listing], fetcher, verify_links=False)
        self.assertEqual(fetcher.checked, [])
        self.assertEqual(listing.link_status, "unchecked")

        self.run_agent([listing], None)
        self.assertEqual(listing.link_status, "unchecked")

    def test_budget_caps_requests(self):
        from tests.helpers import make_listing

        listings = []
        verdicts = {}
        for index in range(5):
            item = make_listing(id=f"l{index}", title=f"Wohnung {index}")
            item.url = f"https://www.immobilienscout24.de/expose/9{index}"
            verdicts[item.url] = True
            listings.append(item)
        fetcher = self.StubFetcher(verdicts)
        self.run_agent(listings, fetcher, max_link_checks=2)
        self.assertEqual(len(fetcher.checked), 2)


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
