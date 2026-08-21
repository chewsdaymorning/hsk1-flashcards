import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from wohnungssuche.models import ApprovalStatus, PlatformStatus
from wohnungssuche.storage import Storage
from tests.helpers import make_listing


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.storage.close()
        self.tmp.cleanup()

    def test_new_listings_are_reported_once(self):
        listing = make_listing()
        self.assertEqual(self.storage.save_listings([listing]), [listing.unique_hash])
        self.assertEqual(self.storage.save_listings([listing]), [])

    def test_round_trip(self):
        listing = make_listing()
        self.storage.upsert_listing(listing)
        restored = self.storage.get_listing(listing.unique_hash)
        self.assertEqual(restored.url, listing.url)
        self.assertEqual(restored.rooms, listing.rooms)
        self.assertIsNone(self.storage.get_listing("nope"))

    def test_approval_workflow(self):
        listing = make_listing()
        self.storage.upsert_listing(listing)
        self.storage.request_approval(listing, note="vorgeschlagen")

        pending = self.storage.approvals(ApprovalStatus.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0][1].id, listing.id)

        self.assertTrue(
            self.storage.set_approval(listing.unique_hash, ApprovalStatus.APPROVED, "ok")
        )
        self.assertEqual(len(self.storage.approvals(ApprovalStatus.PENDING)), 0)
        approved = self.storage.approvals(ApprovalStatus.APPROVED)
        self.assertEqual(approved[0][0]["note"], "ok")
        self.assertIsNotNone(approved[0][0]["decided_at"])

    def test_approval_of_unknown_hash_fails(self):
        self.assertFalse(self.storage.set_approval("nope", ApprovalStatus.APPROVED))

    def test_requesting_approval_twice_keeps_the_decision(self):
        listing = make_listing()
        self.storage.upsert_listing(listing)
        self.storage.request_approval(listing)
        self.storage.set_approval(listing.unique_hash, ApprovalStatus.REJECTED)
        self.storage.request_approval(listing)
        self.assertEqual(len(self.storage.approvals(ApprovalStatus.REJECTED)), 1)

    def test_runs_are_recorded(self):
        now = datetime.now()
        self.storage.record_run(
            started_at=now,
            finished_at=now,
            found=10,
            new_listings=3,
            matches=2,
            scam_flagged=1,
            platforms=[PlatformStatus(platform="is24", success=True, listings_found=10)],
            report_path="reports/x.html",
        )
        runs = self.storage.recent_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["matches"], 2)
        self.assertIn("is24", runs[0]["platforms"])


if __name__ == "__main__":
    unittest.main()
