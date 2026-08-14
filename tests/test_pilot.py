import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_pilot import load_district, population_cells, facilities_near, slugify


class PilotInputTests(unittest.TestCase):
    def test_dhaka_inputs_are_nonempty(self):
        _, district = load_district("Dhaka")
        cells = population_cells(district)
        facilities = facilities_near(district, 0.25)
        self.assertGreater(len(cells), 100)
        self.assertGreater(len(facilities), 10)
        self.assertGreater(sum(cell["population"] for cell in cells), 1_000_000)

    def test_unknown_district_is_rejected(self):
        with self.assertRaises(ValueError):
            load_district("Not a district")

    def test_district_slug_is_url_safe(self):
        self.assertEqual(slugify("Cox's Bazar"), "cox-s-bazar")


if __name__ == "__main__":
    unittest.main()
