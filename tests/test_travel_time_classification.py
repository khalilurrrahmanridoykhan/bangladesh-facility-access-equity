import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module

aggregate_module = import_module("06_aggregate_by_union")


def test_parse_geoshape_builds_closed_polygon():
    # A small square, lat-first per the XForms geoshape convention.
    shape = "23.0 90.0 0 0;23.0 90.1 0 0;23.1 90.1 0 0;23.1 90.0 0 0;23.0 90.0 0 0"
    poly = aggregate_module.parse_geoshape(shape)
    assert poly.is_valid
    assert poly.exterior.coords[0] == poly.exterior.coords[-1]
    # centroid should land inside the square, lon around 90.05, lat around 23.05
    assert 90.0 <= poly.centroid.x <= 90.1
    assert 23.0 <= poly.centroid.y <= 23.1


def make_union_gdf():
    # Two adjacent unit-square unions side by side.
    return gpd.GeoDataFrame(
        {
            "union_code": ["uni_a", "uni_b"],
            "union_name": ["Union A", "Union B"],
            "upazila_name": ["Upazila X", "Upazila X"],
            "district_name": ["District 1", "District 1"],
            "division_name": ["Division 1", "Division 1"],
        },
        geometry=[box(90.0, 23.0, 91.0, 24.0), box(91.0, 23.0, 92.0, 24.0)],
        crs="EPSG:4326",
    )


def test_aggregate_classifies_and_sums_underserved_population():
    cells = pd.DataFrame(
        {
            "lon": [90.5, 90.5, 91.5],
            "lat": [23.5, 23.5, 23.5],
            "population": [100, 50, 200],
            "travel_time_minutes": [30, 150, 10],  # second cell in union A is underserved
            "no_road_connection": [False, False, False],
        }
    )
    summary = aggregate_module.aggregate(cells, make_union_gdf())

    union_a = summary[summary["union_code"] == "uni_a"].iloc[0]
    assert union_a["population"] == 150
    assert union_a["population_underserved"] == 50
    assert union_a["pct_underserved"] == pytest_approx(33.3)

    union_b = summary[summary["union_code"] == "uni_b"].iloc[0]
    assert union_b["population_underserved"] == 0


def test_aggregate_treats_no_road_connection_as_underserved():
    cells = pd.DataFrame(
        {
            "lon": [90.5],
            "lat": [23.5],
            "population": [100],
            "travel_time_minutes": [float("nan")],
            "no_road_connection": [True],
        }
    )
    summary = aggregate_module.aggregate(cells, make_union_gdf())
    union_a = summary[summary["union_code"] == "uni_a"].iloc[0]
    assert union_a["population_underserved"] == 100


def pytest_approx(value, rel=1e-2):
    import pytest

    return pytest.approx(value, rel=rel)


def test_national_totals_includes_cells_with_no_union_match():
    # Simulates the real Dhaka finding: a huge-population cell with a short
    # travel time but no union match should still count toward the national
    # total (and NOT toward underserved, since it's well-served).
    cells = pd.DataFrame(
        {
            "lon": [90.4, 90.5],
            "lat": [23.8, 23.5],
            "population": [190000, 50],
            "travel_time_minutes": [5, 150],
            "no_road_connection": [False, False],
        }
    )
    total_pop, total_underserved = aggregate_module.national_totals(cells)
    assert total_pop == 190050
    assert total_underserved == 50
