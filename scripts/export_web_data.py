#!/usr/bin/env python3
"""Create compact, public-facing pilot datasets for the static PWA."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_pilot import facilities_near, load_district


def export(district: str) -> None:
    slug = district.casefold().replace(" ", "-")
    summary_path = ROOT / "outputs" / f"{slug}-summary.json"
    cells_path = ROOT / "outputs" / f"{slug}-access.csv"
    if not summary_path.exists() or not cells_path.exists():
        raise FileNotFoundError(f"Run the {district} pilot before exporting web data")

    feature, geometry = load_district(district)
    facilities = facilities_near(geometry, 0.25)
    cells = []
    with cells_path.open() as source:
        for row in csv.DictReader(source):
            cells.append([
                round(float(row["longitude"]), 5), round(float(row["latitude"]), 5),
                round(float(row["population"])), round(float(row["total_access_time_minutes"]), 1),
                row["over_threshold"].lower() == "true", row["long_road_snap"].lower() == "true",
            ])
    public_facilities = [[
        round(item["longitude"], 5), round(item["latitude"], 5), item["name"], item["type"]
    ] for item in facilities]
    payload = {
        "schema": "facility-access-public-v1",
        "district": district,
        "summary": json.loads(summary_path.read_text()),
        "boundary": feature["geometry"],
        "cells": cells,
        "facilities": public_facilities,
        "cell_fields": ["longitude", "latitude", "population", "access_minutes", "over_120_minutes", "uncertain_road_snap"],
        "facility_fields": ["longitude", "latitude", "name", "type"],
    }
    destination = ROOT / "web" / "data" / f"{slug}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    print(f"Wrote {destination.relative_to(ROOT)} ({destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    for name in ("Dhaka", "Bandarban"):
        export(name)

