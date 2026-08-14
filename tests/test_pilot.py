import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_pilot import load_district, population_cells, facilities_near, slugify

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
PILOT_INPUTS_AVAILABLE = all(
    (RAW / name).exists()
    for name in (
        "geoBoundaries-BGD-ADM2.geojson",
        "bangladesh_healthsites.geojson",
        "bgd_ppp_2020_1km_aggregated.tif",
    )
)


class PilotInputTests(unittest.TestCase):
    @unittest.skipUnless(PILOT_INPUTS_AVAILABLE, "downloaded pilot inputs are not committed")
    def test_dhaka_inputs_are_nonempty(self):
        _, district = load_district("Dhaka")
        cells = population_cells(district)
        facilities = facilities_near(district, 0.25)
        self.assertGreater(len(cells), 100)
        self.assertGreater(len(facilities), 10)
        self.assertGreater(sum(cell["population"] for cell in cells), 1_000_000)

    @unittest.skipUnless((RAW / "geoBoundaries-BGD-ADM2.geojson").exists(), "district boundaries are not committed")
    def test_unknown_district_is_rejected(self):
        with self.assertRaises(ValueError):
            load_district("Not a district")

    def test_district_slug_is_url_safe(self):
        self.assertEqual(slugify("Cox's Bazar"), "cox-s-bazar")


if __name__ == "__main__":
    unittest.main()
