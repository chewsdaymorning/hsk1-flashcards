import unittest

from wohnungssuche.filters import FilterEngine
from tests.helpers import config, make_listing


class TestFilterEngine(unittest.TestCase):
    def setUp(self):
        self.engine = FilterEngine(config())

    def assertRejected(self, listing, fragment):
        reasons = self.engine.evaluate(listing)
        self.assertTrue(reasons, "expected the listing to be rejected")
        self.assertTrue(
            any(fragment.lower() in reason.lower() for reason in reasons),
            f"{fragment!r} not in {reasons}",
        )

    def test_valid_listing_matches(self):
        self.assertEqual(self.engine.evaluate(make_listing()), [])

    def test_too_few_rooms(self):
        self.assertRejected(make_listing(rooms=2.0), "Zimmer")

    def test_too_small(self):
        self.assertRejected(make_listing(area_sqm=65.0), "m²")

    def test_too_expensive(self):
        self.assertRejected(make_listing(warm_rent=1650.0), "über Limit")

    def test_excluded_district(self):
        self.assertRejected(
            make_listing(district="Erbenheim", address="Wandersmannstraße 4, Erbenheim"),
            "Erbenheim",
        )

    def test_mainz_kastel_excluded(self):
        self.assertRejected(
            make_listing(district="Mainz-Kastel", address="Boelckestraße 14, Mainz-Kastel"),
            "Kastel",
        )

    def test_too_far_from_center(self):
        self.assertRejected(make_listing(distance_to_center_km=6.2), "vom Zentrum")

    def test_unknown_distance_is_not_a_rejection(self):
        listing = make_listing(distance_to_center_km=None)
        self.assertEqual(self.engine.evaluate(listing), [])
        self.assertIn(
            "Entfernung zum Zentrum unbekannt – bitte prüfen", self.engine.warnings(listing)
        )

    def test_small_kitchen_from_hint(self):
        self.assertRejected(make_listing(kitchen_size_hint="small"), "Küche")

    def test_small_kitchen_from_text(self):
        self.assertRejected(
            make_listing(kitchen_size_hint="unknown", description="Wohnung mit Pantry"),
            "Küche",
        )

    def test_wg_room_is_excluded(self):
        self.assertRejected(make_listing(title="WG-Zimmer in 3er-WG"), "Mietvertrag")

    def test_sublet_is_excluded(self):
        self.assertRejected(
            make_listing(description="Nur zur Zwischenmiete für 6 Monate"), "Mietvertrag"
        )

    def test_temporary_rental_is_excluded(self):
        self.assertRejected(
            make_listing(description="Wohnen auf Zeit, möbliert"), "Mietvertrag"
        )

    def test_scam_flagged_is_excluded(self):
        listing = make_listing()
        listing.is_scam_flagged = True
        listing.scam_reasons = ["western_union"]
        self.assertRejected(listing, "Scam-Verdacht")

    def test_parking_is_only_a_note(self):
        listing = make_listing(has_parking=False)
        self.assertEqual(self.engine.evaluate(listing), [])
        self.assertIn("Kein Stellplatz erwähnt (nice-to-have)", self.engine.warnings(listing))

    def test_estimated_warm_rent_is_noted(self):
        listing = make_listing(warm_rent_is_estimated=True)
        self.assertEqual(self.engine.evaluate(listing), [])
        self.assertTrue(
            any("geschätzt" in note for note in self.engine.warnings(listing))
        )


class TestFilterSplit(unittest.TestCase):
    def test_split_and_sorting(self):
        engine = FilterEngine(config())
        cheap = make_listing(id="cheap", warm_rent=1000.0, area_sqm=100.0)
        pricey = make_listing(id="pricey", warm_rent=1500.0, area_sqm=75.0, title="Andere")
        rejected = make_listing(id="small", rooms=1.0, title="Einzimmer")
        matches, non_matches = engine.filter_listings([pricey, cheap, rejected])

        self.assertEqual([item.id for item in matches], ["cheap", "pricey"])
        self.assertEqual([item.id for item in non_matches], ["small"])
        self.assertTrue(all(item.matches_criteria for item in matches))
        self.assertFalse(non_matches[0].matches_criteria)
        self.assertTrue(non_matches[0].exclude_reasons)


if __name__ == "__main__":
    unittest.main()
