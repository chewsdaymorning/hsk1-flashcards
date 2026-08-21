import unittest

from wohnungssuche.validation import ScamDetector, extract_contact
from tests.helpers import config, make_listing


class TestScamDetector(unittest.TestCase):
    def setUp(self):
        self.detector = ScamDetector(config())

    def test_clean_listing_is_not_flagged(self):
        listing = make_listing()
        self.assertEqual(self.detector.check(listing), [])
        self.assertFalse(listing.is_scam_flagged)

    def test_western_union(self):
        listing = make_listing(description="Zahlung bitte per Western Union.")
        self.assertIn("western_union", self.detector.check(listing))

    def test_vorkasse(self):
        listing = make_listing(description="Die Kaution ist als Vorkasse zu leisten.")
        self.assertIn("vorkasse", self.detector.check(listing))

    def test_landlord_abroad_and_key_by_mail(self):
        listing = make_listing(
            description=(
                "Ich befinde mich derzeit im Ausland, die Schlüssel werden per Post "
                "zugesandt."
            )
        )
        reasons = self.detector.check(listing)
        self.assertIn("landlord_abroad", reasons)
        self.assertIn("key_by_mail", reasons)

    def test_urgency_and_id_documents(self):
        listing = make_listing(
            title="Traumwohnung nur heute!",
            description="Bitte zuerst eine Ausweiskopie senden.",
        )
        reasons = self.detector.check(listing)
        self.assertIn("urgency_pressure", reasons)
        self.assertIn("id_documents_upfront", reasons)

    def test_unrealistic_price(self):
        listing = make_listing(warm_rent=450.0, area_sqm=95.0)
        self.assertIn("unrealistic_price", self.detector.check(listing))

    def test_inconsistent_data(self):
        listing = make_listing(warm_rent=1200.0, cold_rent=1300.0)
        self.assertIn("inconsistent_data", self.detector.check(listing))

    def test_missing_contact_is_only_flagged_after_detail_fetch(self):
        # Result cards never carry contact data - flagging them would flag
        # every single listing, which is exactly the old bug.
        listing = make_listing()
        self.assertNotIn("no_contact", self.detector.check(listing))

        listing = make_listing(details_fetched=True)
        self.assertIn("no_contact", self.detector.check(listing))

        listing = make_listing(details_fetched=True, contact_email="a@b.de")
        self.assertNotIn("no_contact", self.detector.check(listing))

    def test_check_all_counts_flagged(self):
        listings = [make_listing(), make_listing(description="Vorkasse per Bitcoin")]
        _, flagged = self.detector.check_all(listings)
        self.assertEqual(flagged, 1)


class TestContactExtraction(unittest.TestCase):
    def test_extracts_email_and_phone(self):
        email, phone = extract_contact(
            "Bitte melden bei max.mustermann@example-immo.de oder 0611 123456."
        )
        self.assertEqual(email, "max.mustermann@example-immo.de")
        self.assertTrue(phone.startswith("0611"))

    def test_returns_none_when_absent(self):
        self.assertEqual(extract_contact("Kein Kontakt hinterlegt."), (None, None))


if __name__ == "__main__":
    unittest.main()
