"""
Reads the WorldPop 1km population raster and emits one row per populated
grid cell as (lon, lat, population). Most of the raster is water/uninhabited
and gets skipped -- this keeps the downstream OSRM routing step to a
tractable number of points instead of every raster cell nationwide.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

MIN_POPULATION_PER_CELL = 1.0  # skip cells with less than one person

# Real, independently-known figure to sanity-check the raster read against
# (Bangladesh's population is well documented -- roughly 170-173 million as
# of the 2020s). Not a hard assertion (the raster's own modeled total won't
# match a census exactly), just a plausibility bound.
EXPECTED_POPULATION_RANGE = (140_000_000, 200_000_000)


def extract_populated_cells(tif_path: Path) -> pd.DataFrame:
    with rasterio.open(tif_path) as src:
        band = src.read(1, masked=True)
        transform = src.transform

        rows, cols = np.where((~band.mask) & (band.data >= MIN_POPULATION_PER_CELL))
        pops = band.data[rows, cols]

        xs, ys = rasterio.transform.xy(transform, rows, cols)

    return pd.DataFrame({"lon": xs, "lat": ys, "population": pops})


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tif_path = RAW_DIR / "population_2020_1km.tif"

    df = extract_populated_cells(tif_path)
    total_population = df["population"].sum()

    print(f"Populated cells: {len(df):,}")
    print(f"Total population (summed from raster): {total_population:,.0f}")

    low, high = EXPECTED_POPULATION_RANGE
    if not (low <= total_population <= high):
        print(
            f"[WARNING] Summed population {total_population:,.0f} is outside the expected "
            f"plausible range ({low:,}-{high:,}) for Bangladesh -- investigate before trusting this grid."
        )
    else:
        print(f"Plausibility check passed: within expected range ({low:,}-{high:,}).")

    out_path = PROCESSED_DIR / "population_grid.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df):,} rows to {out_path}")


if __name__ == "__main__":
    main()
