import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module

prepare_facilities = import_module("03_prepare_facilities")


def make_gdf(points):
    return gpd.GeoDataFrame(geometry=[Point(lon, lat) for lon, lat in points], crs="EPSG:4326")


def test_clean_facilities_drops_out_of_bounds_points():
    gdf = make_gdf([(90.0, 23.7), (0.0, 0.0), (200.0, 90.0)])  # Dhaka-ish, then two bogus points
    cleaned = prepare_facilities.clean_facilities(gdf)
    assert len(cleaned) == 1


def test_clean_facilities_deduplicates_exact_coordinates():
    gdf = make_gdf([(90.0, 23.7), (90.0, 23.7), (90.1, 23.8)])
    cleaned = prepare_facilities.clean_facilities(gdf)
    assert len(cleaned) == 2


def test_coverage_gap_report_full_match():
    lged = make_gdf([(90.0, 23.7), (91.0, 24.0)])
    healthsites = make_gdf([(90.0001, 23.7001)])  # a few meters from the first LGED point
    report = prepare_facilities.coverage_gap_report(lged, healthsites)
    assert report["matched_within_1km"] == 1
    assert report["unmatched"] == 0
    assert report["coverage_pct"] == 100.0


def test_coverage_gap_report_no_match():
    lged = make_gdf([(90.0, 23.7)])
    healthsites = make_gdf([(92.5, 26.5)])  # far away, well outside 1km
    report = prepare_facilities.coverage_gap_report(lged, healthsites)
    assert report["matched_within_1km"] == 0
    assert report["unmatched"] == 1
    assert report["coverage_pct"] == 0.0


def test_coverage_gap_report_handles_empty_healthsites():
    lged = make_gdf([(90.0, 23.7)])
    healthsites = make_gdf([])
    report = prepare_facilities.coverage_gap_report(lged, healthsites)
    assert report["healthsites_count"] == 0


def test_merge_facility_sources_drops_near_duplicates_but_keeps_unique():
    lged = make_gdf([(90.0, 23.7)])
    healthsites = make_gdf([(90.0001, 23.7001), (92.0, 25.0)])  # one near-dup, one genuinely distinct
    merged = prepare_facilities.merge_facility_sources(lged, healthsites)
    assert len(merged) == 2  # the 1 LGED point + the 1 genuinely-distinct Healthsites point
