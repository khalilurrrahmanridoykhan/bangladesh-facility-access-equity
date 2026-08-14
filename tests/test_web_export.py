import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicWebDataTests(unittest.TestCase):
    def test_exported_pilots_match_public_schema(self):
        for district in ("dhaka", "bandarban"):
            payload = json.loads((ROOT / "web" / "data" / f"{district}.json").read_text())
            self.assertEqual(payload["schema"], "facility-access-public-v1")
            self.assertGreater(len(payload["cells"]), 100)
            self.assertGreater(len(payload["facilities"]), 10)
            self.assertEqual(len(payload["cell_fields"]), len(payload["cells"][0]))
            self.assertEqual(len(payload["facility_fields"]), len(payload["facilities"][0]))
            self.assertEqual(payload["summary"]["district"].casefold(), district)

    def test_pwa_core_assets_exist(self):
        for name in ("index.html", "app.js", "styles.css", "manifest.webmanifest", "service-worker.js", "icon.svg", "tile-fallback.svg"):
            self.assertGreater((ROOT / "web" / name).stat().st_size, 0)

    def test_feedback_dialog_and_directions_are_present(self):
        html = (ROOT / "web" / "index.html").read_text()
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn('id="reportDialog"', html)
        self.assertIn("shasthopath-reports", javascript)
        self.assertIn("google.com/maps/dir", javascript)
        self.assertIn('/api/reports', javascript)

    def test_leaflet_is_served_locally(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn("vendor/leaflet/leaflet.css", html)
        self.assertIn("vendor/leaflet/leaflet.js", html)
        self.assertNotIn("unpkg.com/leaflet", html)
        self.assertGreater((ROOT / "web" / "vendor" / "leaflet" / "leaflet.css").stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
