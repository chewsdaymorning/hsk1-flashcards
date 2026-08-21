import json
import tempfile
import unittest
from pathlib import Path

from wohnungssuche.models import PlatformStatus
from wohnungssuche.reporting import ReportGenerator, format_eur, format_number, render_enquiry
from tests.helpers import config, make_listing


class TestFormatting(unittest.TestCase):
    def test_currency_and_numbers(self):
        self.assertEqual(format_eur(1420.0), "1.420 €")
        self.assertEqual(format_eur(None), "–")
        self.assertEqual(format_number(3.5), "3,5")
        self.assertEqual(format_number(86.0), "86")
        self.assertEqual(format_number(1234.5), "1.234,5")


class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name)
        self.generator = ReportGenerator(config(), self.output)

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, **kwargs):
        defaults = dict(
            matches=[make_listing(image_urls=["https://pictures.immobilienscout24.de/a.jpg"])],
            non_matches=[],
            flagged=[],
            platform_status=[PlatformStatus(platform="is24", success=True, listings_found=1)],
        )
        defaults.update(kwargs)
        html_path, json_path = self.generator.generate(**defaults)
        return html_path, json_path, html_path.read_text(encoding="utf-8")

    def test_writes_html_json_and_css(self):
        html_path, json_path, html = self.render()
        self.assertTrue(html_path.exists())
        self.assertTrue(json_path.exists())
        self.assertTrue((self.output / "latest.html").exists())
        self.assertTrue((self.output / "static" / "style.css").exists())
        self.assertIn("Wohnungssuche", html)

    def test_links_and_images_are_real(self):
        _, _, html = self.render()
        self.assertIn('href="https://www.immobilienscout24.de/expose/123456789"', html)
        self.assertIn('src="https://pictures.immobilienscout24.de/a.jpg"', html)
        self.assertNotIn("example.com", html)
        self.assertNotIn("picsum", html)

    def test_missing_image_falls_back(self):
        _, _, html = self.render(matches=[make_listing(image_urls=[])])
        self.assertIn("Kein Bild im Inserat", html)

    def test_no_send_functionality_is_offered(self):
        _, _, html = self.render()
        self.assertIn("Keine automatische Kontaktaufnahme", html)
        self.assertIn("disabled", html)

    def test_html_in_listing_text_is_escaped(self):
        _, _, html = self.render(
            matches=[make_listing(title="<script>alert('x')</script> Wohnung")]
        )
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_scam_section_is_separate_from_non_matches(self):
        scam = make_listing(id="scam", title="Traumwohnung", warm_rent=450.0)
        scam.is_scam_flagged = True
        scam.scam_reasons = ["western_union"]
        scam.exclude_reasons = ["Scam-Verdacht"]
        _, json_path, html = self.render(non_matches=[scam], flagged=[scam])
        self.assertIn("Scam-Verdacht (1)", html)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["flagged"]), 1)
        self.assertEqual(payload["non_matches"], [])

    def test_json_snapshot_contains_criteria_and_matches(self):
        _, json_path, _ = self.render()
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["criteria"]["max_warm_rent_eur"], 1600.0)
        self.assertEqual(len(payload["matches"]), 1)
        self.assertEqual(payload["platform_status"][0]["platform"], "is24")


class TestEnquiryDraft(unittest.TestCase):
    def test_draft_mentions_tenants_and_is_marked_as_draft(self):
        text = render_enquiry(config(), make_listing())
        self.assertIn("Paar, Nichtraucher, keine Haustiere", text)
        self.assertIn("NICHT verschickt", text)
        self.assertIn("https://www.immobilienscout24.de/expose/123456789", text)


if __name__ == "__main__":
    unittest.main()
