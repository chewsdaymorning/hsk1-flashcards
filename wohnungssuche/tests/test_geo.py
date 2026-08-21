import unittest

from wohnungssuche.geo import (
    Geocoder,
    coords_for_district,
    detect_district,
    haversine_km,
    normalise,
)


class TestDistance(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(haversine_km(50.0826, 8.24, 50.0826, 8.24), 0.0)

    def test_known_distance(self):
        # City centre to Biebrich is roughly 4.8 km.
        self.assertAlmostEqual(haversine_km(50.0826, 8.24, 50.04, 8.23), 4.8, delta=0.3)


class TestDistricts(unittest.TestCase):
    def test_normalise_umlauts(self):
        self.assertEqual(normalise("Kostheim-Süd Straße"), "kostheim-sued strasse")

    def test_detects_district_in_address(self):
        self.assertEqual(
            detect_district("Hauptstr. 5, 65205 Wiesbaden-Erbenheim"), "Erbenheim"
        )

    def test_prefers_longest_match(self):
        self.assertEqual(detect_district("Wiesbaden, Mainz-Kastel"), "Mainz-Kastel")

    def test_does_not_match_inside_other_words(self):
        # "Kastellweg" must not be read as the excluded district "Kastel".
        self.assertNotEqual(detect_district("Am Kastellweg 3, Wiesbaden"), "Kastel")

    def test_coords_lookup_is_umlaut_tolerant(self):
        self.assertIsNotNone(coords_for_district("Südost"))
        self.assertIsNone(coords_for_district("Frankfurt"))


class TestGeocoder(unittest.TestCase):
    def test_offline_geocoder_uses_district_table(self):
        geocoder = Geocoder(allow_network=False)
        self.assertEqual(
            geocoder.geocode("Bertramstraße 12", "Rheingauviertel"),
            coords_for_district("Rheingauviertel"),
        )

    def test_offline_geocoder_returns_none_for_unknown(self):
        geocoder = Geocoder(allow_network=False)
        self.assertIsNone(geocoder.geocode("Irgendwo 1, Berlin"))


if __name__ == "__main__":
    unittest.main()
