"""End-to-end: the e-mail source feeding the full agent pipeline."""

import tempfile
import unittest
from pathlib import Path

from wohnungssuche.agents import Orchestrator
from wohnungssuche.agents.orchestrator import build_scrapers
from tests.helpers import config


class TestEmailSourceThroughPipeline(unittest.TestCase):
    def test_email_platform_flows_to_report(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        search_config = config(fetch_details=False, platforms=["email"])
        result = Orchestrator(
            config=search_config,
            storage=None,
            output_dir=Path(tmp.name),
            use_mock=True,
        ).run()

        statuses = {s.platform: s for s in result.platform_status}
        self.assertIn("email", statuses)
        self.assertTrue(statuses["email"].success)
        self.assertEqual(statuses["email"].listings_found, 3)

        everything = result.matches + result.non_matches
        self.assertEqual(len(everything), 3)
        # Listings carry the real portal, not "email".
        self.assertEqual(
            sorted({listing.platform for listing in everything}),
            ["immowelt", "is24"],
        )
        html = Path(result.report_path).read_text(encoding="utf-8")
        for listing in everything:
            self.assertIn(listing.url, html)

    def test_live_email_without_credentials_is_skipped_cleanly(self):
        scrapers = build_scrapers(
            config(platforms=["email"], imap_host="", imap_user=""), use_mock=False
        )
        self.assertEqual(scrapers, {})

    def test_mixed_platforms_deduplicate_across_sources(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        search_config = config(
            fetch_details=False,
            platforms=["is24", "immowelt", "kleinanzeigen", "email"],
        )
        result = Orchestrator(
            config=search_config,
            storage=None,
            output_dir=Path(tmp.name),
            use_mock=True,
        ).run()
        everything = result.matches + result.non_matches
        hashes = [listing.unique_hash for listing in everything]
        self.assertEqual(len(hashes), len(set(hashes)))
        # 12 from the portal fixtures + 3 from the mail fixtures (distinct ids).
        self.assertEqual(len(everything), 15)


if __name__ == "__main__":
    unittest.main()
