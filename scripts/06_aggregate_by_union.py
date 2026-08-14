"""
Spatially joins every computed grid-cell travel time to the Union polygon
it falls inside, then aggregates population and "underserved" (>2hr from
the nearest facility) population per Union.

Reuses the already-built, already-validated Union boundary geometry from
the bangladesh-geo-service project instead of re-deriving anything from
shapefiles a third time.
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "output"

ADMIN_GEO_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "onehealth-platform" / "bangladesh-geo-service" / "data" / "admin-geo.json"
)

UNDERSERVED_THRESHOLD_MINUTES = 120


def parse_geoshape(geoshape: str) -> Polygon:
    """XForms geoshape string -> shapely Polygon.
    Format: 'lat lon alt acc;lat lon alt acc;...' (ring closed, first point repeated last).
    Confirmed point order (lat first) against the ODK XForms spec and
    KoboToolbox's own worked examples during the xlsform project."""
    points = []
    for part in geoshape.split(";"):
        fields = part.strip().split(" ")
        lat, lon = float(fields[0]), float(fields[1])
        points.append((lon, lat))  # shapely wants (x=lon, y=lat)
    return Polygon(points)


def load_union_polygons(admin_geo_path: Path) -> gpd.GeoDataFrame:
    units = json.loads(admin_geo_path.read_text())
    by_code = {u["code"]: u for u in units}

    rows = []
    for u in units:
        if u["level"] != "union" or "geometry" not in u:
            continue
        upazila = by_code.get(u["parentCode"])
        district = by_code.get(upazila["parentCode"]) if upazila else None
        division = by_code.get(district["parentCode"]) if district else None
        rows.append(
            {
                "union_code": u["code"],
                "union_name": u["name"],
                "upazila_name": upazila["name"] if upazila else None,
                "district_name": district["name"] if district else None,
                "division_name": division["name"] if division else None,
                "geometry": parse_geoshape(u["geometry"]),
            }
        )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def aggregate(cell_travel_times: pd.DataFrame, unions: gpd.GeoDataFrame) -> pd.DataFrame:
    cells = gpd.GeoDataFrame(
        cell_travel_times,
        geometry=[Point(lon, lat) for lon, lat in zip(cell_travel_times["lon"], cell_travel_times["lat"])],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(cells, unions[["union_code", "union_name", "upazila_name", "district_name", "division_name", "geometry"]],
                        how="left", predicate="within")

    joined["is_underserved"] = (~joined["no_road_connection"]) & (
        joined["travel_time_minutes"] > UNDERSERVED_THRESHOLD_MINUTES
    )
    # Cells with no road connection at all are treated as underserved too --
    # being unreachable by the mapped road network is at least as bad as
    # being >2hr away, and silently excluding them would understate the gap.
    joined.loc[joined["no_road_connection"], "is_underserved"] = True

    # Precomputed as its own column (population where underserved, else 0)
    # rather than an index-aligned lookup inside the groupby -- sjoin can
    # produce a non-unique index, which made a `.loc[s.index]` lookup inside
    # an agg lambda silently misalign on the real ~180k-row dataset.
    joined["population_if_underserved"] = joined["population"].where(joined["is_underserved"], 0)

    grouped = joined.groupby("union_code", dropna=True).agg(
        union_name=("union_name", "first"),
        upazila_name=("upazila_name", "first"),
        district_name=("district_name", "first"),
        division_name=("division_name", "first"),
        population=("population", "sum"),
        population_underserved=("population_if_underserved", "sum"),
        cells_no_road_connection=("no_road_connection", "sum"),
    ).reset_index()

    grouped["pct_underserved"] = (
        100 * grouped["population_underserved"] / grouped["population"]
    ).round(1)

    unmatched = joined[joined["union_code"].isna()]
    if len(unmatched):
        print(
            f"[NOTE] {len(unmatched):,} population cells ({unmatched['population'].sum():,.0f} people) "
            f"fell outside every union polygon and are excluded from the union-level breakdown below. "
            f"This is a real structural gap, not a bug: Bangladesh's City Corporations (Dhaka, Chattogram, "
            f"etc.) are subdivided into Wards, not Unions, so they're absent from Union boundary data by "
            f"design. See the national total (computed separately, over ALL cells) for the true nationwide figure."
        )

    return grouped.sort_values("pct_underserved", ascending=False).reset_index(drop=True)


def national_totals(cell_travel_times: pd.DataFrame) -> tuple[float, float]:
    """Computed over ALL cells, independent of the union-level breakdown --
    the union join legitimately excludes City Corporation areas (see
    `aggregate`'s note), so the union-level sums alone would understate the
    true national population and misrepresent the true national percentage."""
    underserved = cell_travel_times["no_road_connection"] | (
        cell_travel_times["travel_time_minutes"] > UNDERSERVED_THRESHOLD_MINUTES
    )
    total_population = cell_travel_times["population"].sum()
    underserved_population = cell_travel_times.loc[underserved, "population"].sum()
    return total_population, underserved_population


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cell_travel_times = pd.read_csv(PROCESSED_DIR / "cell_travel_times.csv")
    unions = load_union_polygons(ADMIN_GEO_PATH)
    print(f"Loaded {len(unions):,} union polygons")

    summary = aggregate(cell_travel_times, unions)

    total_population, total_underserved = national_totals(cell_travel_times)
    print(f"\nNational (all cells, including City Corporation/Ward areas not covered by Union "
          f"boundaries): {total_underserved:,.0f} / {total_population:,.0f} "
          f"({100 * total_underserved / total_population:.2f}%) population >2hr from nearest facility "
          f"or with no road connection at all")

    print("\nMost underserved unions (rural/municipality areas only -- City Corporations excluded, see note above):")
    print(summary.head(10)[["union_name", "district_name", "population", "pct_underserved"]].to_string(index=False))

    out_path = OUTPUT_DIR / "union_access_summary.csv"
    summary.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
