#!/usr/bin/env python3
"""Run every Bangladesh district with resume support against a live OSRM service."""

from __future__ import annotations

import argparse
import json
import time

from run_pilot import (
    OUTPUTS, compute_access, facilities_near, load_boundaries, load_district,
    population_cells, write_outputs,
    slugify,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osrm-url", default="http://127.0.0.1:5001")
    parser.add_argument("--threshold-minutes", type=float, default=120)
    parser.add_argument("--walking-speed-kmh", type=float, default=3.0)
    parser.add_argument("--max-road-snap-m", type=float, default=2000)
    parser.add_argument("--facility-buffer-degrees", type=float, default=0.25)
    parser.add_argument("--source-batch", type=int, default=150)
    parser.add_argument("--destination-batch", type=int, default=300)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--district", action="append", help="Run only named districts; may be repeated")
    args = parser.parse_args()

    available = sorted(feature["properties"]["shapeName"] for feature in load_boundaries()["features"])
    districts = args.district or available
    unknown = sorted(set(districts) - set(available))
    if unknown:
        raise ValueError(f"Unknown districts: {', '.join(unknown)}")

    started = time.monotonic()
    completed, skipped, failed = [], [], []
    for index, district in enumerate(districts, 1):
        slug = slugify(district)
        summary_path = OUTPUTS / f"{slug}-summary.json"
        csv_path = OUTPUTS / f"{slug}-access.csv"
        if not args.force and summary_path.exists() and csv_path.exists():
            print(f"[{index}/{len(districts)}] {district}: already complete", flush=True)
            skipped.append(district)
            continue
        print(f"[{index}/{len(districts)}] {district}: loading inputs", flush=True)
        try:
            feature, geometry = load_district(district)
            cells = population_cells(geometry)
            facilities = facilities_near(geometry, args.facility_buffer_degrees)
            if not cells or not facilities:
                raise RuntimeError(f"found {len(cells)} cells and {len(facilities)} facilities")
            print(f"[{index}/{len(districts)}] {district}: routing {len(cells)} cells to {len(facilities)} facilities", flush=True)
            compute_access(cells, facilities, args.osrm_url, args.source_batch, args.destination_batch, args.walking_speed_kmh)
            summary = write_outputs(feature, district, cells, facilities, args.threshold_minutes, args.max_road_snap_m, args.walking_speed_kmh)
            print(f"[{index}/{len(districts)}] {district}: {summary['percent_population_over_threshold']}% over threshold", flush=True)
            completed.append(district)
        except Exception as error:
            print(f"[{index}/{len(districts)}] {district}: FAILED: {error}", flush=True)
            failed.append({"district": district, "error": str(error)})

    result = {
        "districts_requested": len(districts), "completed": completed, "skipped": skipped,
        "failed": failed, "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "national-run.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
