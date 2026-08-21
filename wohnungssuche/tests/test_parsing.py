import unittest

from wohnungssuche.config import SearchConfig
from wohnungssuche.parsing import (
    detect_features,
    kitchen_size_hint,
    parse_area,
    parse_german_number,
    parse_labeled_price,
    parse_price,
    parse_rooms,
)


class TestNumbers(unittest.TestCase):
    def test_german_formats(self):
        self.assertEqual(parse_german_number("1.234,56"), 1234.56)
        self.assertEqual(parse_german_number("1.234"), 1234.0)
        self.assertEqual(parse_german_number("980"), 980.0)
        self.assertEqual(parse_german_number("3,5"), 3.5)
        self.assertIsNone(parse_german_number("keine Angabe"))

    def test_prices(self):
        self.assertEqual(parse_price("1.450,50 € warm"), 1450.5)
        self.assertEqual(parse_price("980 EUR"), 980.0)
        self.assertIsNone(parse_price("auf Anfrage"))

    def test_rooms_and_area(self):
        self.assertEqual(parse_rooms("3-Zimmer-Wohnung"), 3.0)
        self.assertEqual(parse_rooms("3,5 Zi."), 3.5)
        self.assertEqual(parse_area("85,5 m²"), 85.5)
        self.assertEqual(parse_area("110 qm"), 110.0)
        self.assertIsNone(parse_area("keine Angabe"))

    def test_labeled_price_both_orders(self):
        text = "Kaltmiete: 1.200 € Warmmiete 1.480,50 €"
        self.assertEqual(parse_labeled_price(text, ["Warmmiete"]), 1480.5)
        self.assertEqual(parse_labeled_price(text, ["Kaltmiete"]), 1200.0)
        self.assertEqual(parse_labeled_price("1.200 € Kaltmiete", ["Kaltmiete"]), 1200.0)
        self.assertIsNone(parse_labeled_price("1.200 €", ["Warmmiete"]))


class TestFeatures(unittest.TestCase):
    def test_feature_detection(self):
        features = detect_features("Wohnung mit Balkon, EBK, Tiefgarage und Aufzug")
        self.assertTrue(features["has_balcony"])
        self.assertTrue(features["has_ebk"])
        self.assertTrue(features["has_parking"])
        self.assertTrue(features["has_elevator"])
        self.assertFalse(features["has_garden"])

    def test_kitchen_hints(self):
        terms = SearchConfig().small_kitchen_terms
        self.assertEqual(kitchen_size_hint("Wohnung mit Kochnische", terms), "small")
        self.assertEqual(kitchen_size_hint("Miniküche vorhanden", terms), "small")
        self.assertEqual(kitchen_size_hint("große Wohnküche", terms), "large")
        self.assertEqual(kitchen_size_hint("mit EBK", terms), "ebk_unknown")
        self.assertEqual(kitchen_size_hint("Wohnung im Grünen", terms), "unknown")


if __name__ == "__main__":
    unittest.main()
