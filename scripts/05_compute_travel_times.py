"""
For every populated grid cell, finds the real road-network travel time (via
a locally-running osrm-routed) to the nearest health facility.

Straight-line distance is used only as a cheap pre-filter to keep each
OSRM /table call small (a handful of candidate facilities per cell, not
every one of the ~9,400 facilities nationwide) -- the actual travel time
used downstream always comes from OSRM's real road-network routing, never
from the straight-line prefilter itself.

Requires osrm-routed to already be running (see scripts/02_build_osrm_graph.sh).
"""

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

OSRM_BASE_URL = "http://localhost:5050"  # 5000 is often taken by macOS AirPlay Receiver
K_NEAREST_CANDIDATES = 8  # straight-line-nearest facilities considered per cell
BATCH_SIZE = 50  # population cells per OSRM /table call


def to_mercator_xy(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Cheap equirectangular-ish projection good enough for a nearest-neighbor
    prefilter over Bangladesh's small extent -- not used for the real travel
    time, only for picking which facilities to send to OSRM."""
    R = 6371000
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    x = R * lon_rad * np.cos(np.radians(23.7))  # cos(reference latitude)
    y = R * lat_rad
    return np.column_stack([x, y])


def load_inputs(grid_path: Path, facilities_path: Path):
    grid = pd.read_csv(grid_path)
    facilities = gpd.read_file(facilities_path)
    fac_lon = facilities.geometry.x.to_numpy()
    fac_lat = facilities.geometry.y.to_numpy()
    return grid, fac_lon, fac_lat


def query_table(coords: list[tuple[float, float]], sources: list[int], destinations: list[int]) -> list[list[float | None]]:
    coord_str = ";".join(f"{lon},{lat}" for lon, lat in coords)
    url = (
        f"{OSRM_BASE_URL}/table/v1/driving/{coord_str}"
        f"?sources={';'.join(map(str, sources))}"
        f"&destinations={';'.join(map(str, destinations))}"
        f"&annotations=duration"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table error: {data.get('code')} -- {data.get('message', '')}")
    return data["durations"]


def compute_travel_times(grid: pd.DataFrame, fac_lon: np.ndarray, fac_lat: np.ndarray) -> pd.DataFrame:
    fac_xy = to_mercator_xy(fac_lon, fac_lat)
    tree = cKDTree(fac_xy)

    cell_xy = to_mercator_xy(grid["lon"].to_numpy(), grid["lat"].to_numpy())
    # Sort cells by a coarse spatial key so cells in the same batch are
    # geographically close -- keeps each batch's union of candidate
    # facilities small instead of scattering nationwide.
    order = np.lexsort((np.round(grid["lon"].to_numpy(), 1), np.round(grid["lat"].to_numpy(), 1)))
    grid = grid.iloc[order].reset_index(drop=True)
    cell_xy = cell_xy[order]

    n = len(grid)
    k = min(K_NEAREST_CANDIDATES, len(fac_lon))
    _, nearest_idx = tree.query(cell_xy, k=k)
    if k == 1:
        nearest_idx = nearest_idx.reshape(-1, 1)

    results = np.full(n, np.nan)
    unreachable = np.zeros(n, dtype=bool)

    n_batches = (n + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n_batches):
        start, end = b * BATCH_SIZE, min((b + 1) * BATCH_SIZE, n)
        batch_facility_idx = np.unique(nearest_idx[start:end].ravel())

        coords: list[tuple[float, float]] = [
            (grid["lon"].iloc[i], grid["lat"].iloc[i]) for i in range(start, end)
        ]
        source_indices = list(range(len(coords)))
        for fi in batch_facility_idx:
            coords.append((float(fac_lon[fi]), float(fac_lat[fi])))
        dest_indices = list(range(len(source_indices), len(coords)))

        durations = query_table(coords, source_indices, dest_indices)

        for local_i, global_i in enumerate(range(start, end)):
            row = durations[local_i]
            valid = [d for d in row if d is not None]
            if valid:
                results[global_i] = min(valid) / 60.0  # seconds -> minutes
            else:
                unreachable[global_i] = True

        if b % 20 == 0 or b == n_batches - 1:
            print(f"  batch {b + 1}/{n_batches} ({end}/{n} cells)", flush=True)

    grid["travel_time_minutes"] = results
    grid["no_road_connection"] = unreachable
    return grid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("MINLON", "MINLAT", "MAXLON", "MAXLAT"),
                         help="Restrict to a bounding box (for small-scale validation before a full national run)")
    parser.add_argument("--out", default=str(PROCESSED_DIR / "cell_travel_times.csv"))
    args = parser.parse_args()

    grid, fac_lon, fac_lat = load_inputs(
        PROCESSED_DIR / "population_grid.csv", PROCESSED_DIR / "facilities.geojson"
    )

    if args.bbox:
        minlon, minlat, maxlon, maxlat = args.bbox
        grid = grid[grid["lon"].between(minlon, maxlon) & grid["lat"].between(minlat, maxlat)].reset_index(drop=True)
        print(f"Restricted to bbox {args.bbox}: {len(grid):,} cells")

    print(f"Facilities available as candidates: {len(fac_lon):,}")
    print(f"Population cells to process: {len(grid):,}")

    start = time.time()
    result = compute_travel_times(grid, fac_lon, fac_lat)
    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s")

    reachable = result[~result["no_road_connection"]]
    print(f"Reachable cells: {len(reachable):,} / {len(result):,}")
    if len(reachable):
        print(f"Median travel time: {reachable['travel_time_minutes'].median():.1f} min")
        print(f"Cells >120min from nearest facility: {(reachable['travel_time_minutes'] > 120).sum():,}")
    if result["no_road_connection"].any():
        print(f"[NOTE] {result['no_road_connection'].sum():,} cells had no route to any candidate facility "
              f"(likely disconnected from the mapped road network -- e.g. river/char communities; "
              f"a real, documented gap of the car-only profile, not a bug to silently ignore).")

    result.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    try:
        main()
    except requests.ConnectionError:
        print("[ERROR] Could not reach OSRM at " + OSRM_BASE_URL + " -- is osrm-routed running? "
              "See scripts/02_build_osrm_graph.sh for how to start it.", file=sys.stderr)
        sys.exit(1)
