#!/usr/bin/env python3
"""Compute population-weighted access to the nearest mapped health facility."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
import requests
from rasterio.transform import xy
from shapely.geometry import Point, mapping, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTPUTS = ROOT / "outputs"
EXCLUDED_AMENITIES = {"pharmacy", "dentist", "doctors", "optician"}


def load_district(name: str):
    data = json.loads((RAW / "geoBoundaries-BGD-ADM2.geojson").read_text())
    matches = [f for f in data["features"] if f["properties"]["shapeName"].casefold() == name.casefold()]
    if len(matches) != 1:
        available = ", ".join(sorted(f["properties"]["shapeName"] for f in data["features"]))
        raise ValueError(f"District {name!r} not found uniquely. Available: {available}")
    return matches[0], shape(matches[0]["geometry"])


def population_cells(district_geometry) -> list[dict]:
    cells = []
    prepared = prep(district_geometry)
    with rasterio.open(RAW / "bgd_ppp_2020_1km_aggregated.tif") as source:
        band = source.read(1, masked=True)
        rows, cols = np.where((~band.mask) & (band.data > 0))
        longitudes, latitudes = xy(source.transform, rows, cols, offset="center")
        for row, col, lon, lat in zip(rows, cols, longitudes, latitudes):
            if prepared.covers(Point(lon, lat)):
                cells.append({"cell_id": f"r{row}c{col}", "longitude": lon, "latitude": lat, "population": float(band.data[row, col])})
    return cells


def facilities_near(district_geometry, buffer_degrees: float) -> list[dict]:
    data = json.loads((RAW / "bangladesh_healthsites.geojson").read_text())
    search_area = prep(district_geometry.buffer(buffer_degrees))
    facilities = []
    for feature in data["features"]:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        point = shape(geometry).representative_point()
        properties = feature.get("properties", {})
        amenity = str(properties.get("#loc+amenity", "")).strip().lower()
        healthcare = str(properties.get("#meta+healthcare", "")).strip().lower()
        if amenity in EXCLUDED_AMENITIES or healthcare in EXCLUDED_AMENITIES:
            continue
        if not search_area.covers(point):
            continue
        facilities.append({
            "facility_id": str(properties.get("#meta +id") or properties.get("osm_id") or len(facilities)),
            "name": str(properties.get("#loc +name") or "Unnamed facility"),
            "type": healthcare or amenity or "unknown",
            "longitude": point.x,
            "latitude": point.y,
        })
    return facilities


def table(osrm_url: str, sources: list[dict], destinations: list[dict]) -> dict:
    coordinates = sources + destinations
    encoded = ";".join(f"{item['longitude']:.6f},{item['latitude']:.6f}" for item in coordinates)
    source_ids = ";".join(str(index) for index in range(len(sources)))
    destination_ids = ";".join(str(index) for index in range(len(sources), len(coordinates)))
    response = requests.get(
        f"{osrm_url.rstrip('/')}/table/v1/driving/{encoded}",
        params={"sources": source_ids, "destinations": destination_ids, "annotations": "duration"},
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok":
        raise RuntimeError(f"OSRM table failed: {payload}")
    return payload


def compute_access(cells, facilities, osrm_url: str, source_batch: int, destination_batch: int, walking_speed_kmh: float):
    for cell in cells:
        cell.update({
            "driving_time_minutes": None,
            "road_snap_distance_m": None,
            "nearest_facility_road_snap_m": None,
            "first_mile_walking_minutes": None,
            "total_access_time_minutes": None,
            "nearest_facility_id": None,
            "nearest_facility_name": None,
            "nearest_facility_type": None,
        })
    for source_start in range(0, len(cells), source_batch):
        source_group = cells[source_start : source_start + source_batch]
        best = [(math.inf, None, None, None) for _ in source_group]
        for destination_start in range(0, len(facilities), destination_batch):
            destination_group = facilities[destination_start : destination_start + destination_batch]
            payload = table(osrm_url, source_group, destination_group)
            durations = payload["durations"]
            snapped_destinations = payload.get("destinations", [])
            for row_index, snapped_source in enumerate(payload.get("sources", [])):
                distance = snapped_source.get("distance")
                if distance is not None:
                    source_group[row_index]["road_snap_distance_m"] = round(float(distance), 1)
            for row_index, row in enumerate(durations):
                for column_index, seconds in enumerate(row):
                    if seconds is not None:
                        destination_snap = snapped_destinations[column_index].get("distance")
                        destination_snap = float(destination_snap or 0)
                        score = seconds + destination_snap / 1000 / walking_speed_kmh * 3600
                        if score < best[row_index][0]:
                            best[row_index] = (score, seconds, destination_group[column_index], destination_snap)
        for cell, (_, seconds, facility, facility_snap) in zip(source_group, best):
            if facility is not None:
                population_snap = cell["road_snap_distance_m"] or 0
                facility_snap = float(facility_snap or 0)
                walking_minutes = (population_snap + facility_snap) / 1000 / walking_speed_kmh * 60
                driving_minutes = seconds / 60
                cell.update({
                    "driving_time_minutes": round(driving_minutes, 2),
                    "nearest_facility_road_snap_m": round(facility_snap, 1),
                    "first_mile_walking_minutes": round(walking_minutes, 2),
                    "total_access_time_minutes": round(driving_minutes + walking_minutes, 2),
                    "nearest_facility_id": facility["facility_id"],
                    "nearest_facility_name": facility["name"],
                    "nearest_facility_type": facility["type"],
                })
        print(f"Routed {min(source_start + source_batch, len(cells))}/{len(cells)} population cells", flush=True)
    return cells


def write_outputs(district_feature, district_name: str, cells: list[dict], facilities: list[dict], threshold: float, max_snap_distance: float, walking_speed_kmh: float):
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    slug = district_name.casefold().replace(" ", "-")
    for cell in cells:
        duration = cell["total_access_time_minutes"]
        cell["over_threshold"] = duration is not None and duration > threshold
        cell["reachable"] = duration is not None
        cell["long_road_snap"] = cell["road_snap_distance_m"] is None or cell["road_snap_distance_m"] > max_snap_distance

    fields = list(cells[0])
    with (OUTPUTS / f"{slug}-access.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(cells)

    collection = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(Point(cell["longitude"], cell["latitude"])), "properties": {k: v for k, v in cell.items() if k not in {"longitude", "latitude"}}} for cell in cells],
    }
    (OUTPUTS / f"{slug}-access.geojson").write_text(json.dumps(collection) + "\n")

    total_population = sum(cell["population"] for cell in cells)
    reachable_population = sum(cell["population"] for cell in cells if cell["reachable"])
    underserved_population = sum(cell["population"] for cell in cells if cell["over_threshold"])
    long_snap_population = sum(cell["population"] for cell in cells if cell["long_road_snap"])
    weighted_driving_minutes = sum(cell["population"] * cell["driving_time_minutes"] for cell in cells if cell["reachable"])
    weighted_access_minutes = sum(cell["population"] * cell["total_access_time_minutes"] for cell in cells if cell["reachable"])
    summary = {
        "district": district_name,
        "population_year": 2020,
        "population_cells": len(cells),
        "candidate_facilities": len(facilities),
        "excluded_facility_types": sorted(EXCLUDED_AMENITIES),
        "threshold_minutes": threshold,
        "walking_speed_kmh": walking_speed_kmh,
        "max_acceptable_road_snap_m": max_snap_distance,
        "estimated_population": round(total_population),
        "reachable_population": round(reachable_population),
        "unreachable_population": round(total_population - reachable_population),
        "population_over_threshold": round(underserved_population),
        "percent_population_over_threshold": round(100 * underserved_population / total_population, 3) if total_population else None,
        "population_with_long_road_snap": round(long_snap_population),
        "percent_population_with_long_road_snap": round(100 * long_snap_population / total_population, 3) if total_population else None,
        "maximum_road_snap_m": round(max(cell["road_snap_distance_m"] or 0 for cell in cells), 1),
        "population_weighted_mean_driving_minutes": round(weighted_driving_minutes / reachable_population, 2) if reachable_population else None,
        "population_weighted_mean_access_minutes": round(weighted_access_minutes / reachable_population, 2) if reachable_population else None,
    }
    (OUTPUTS / f"{slug}-summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    boundary = shape(district_feature["geometry"])
    fig, axis = plt.subplots(figsize=(8, 8))
    geometries = list(boundary.geoms) if boundary.geom_type == "MultiPolygon" else [boundary]
    for polygon in geometries:
        x, y = polygon.exterior.xy
        axis.plot(x, y, color="#334155", linewidth=1)
    scatter = axis.scatter(
        [cell["longitude"] for cell in cells], [cell["latitude"] for cell in cells],
        c=[cell["total_access_time_minutes"] if cell["total_access_time_minutes"] is not None else threshold * 1.25 for cell in cells],
        s=[max(4, min(80, math.sqrt(cell["population"]))) for cell in cells], cmap="RdYlGn_r", vmin=0, vmax=threshold,
        alpha=0.75, linewidths=0,
    )
    axis.scatter([f["longitude"] for f in facilities], [f["latitude"] for f in facilities], marker="+", s=16, color="#2563eb", label="Candidate facilities")
    long_snap_cells = [cell for cell in cells if cell["long_road_snap"]]
    if long_snap_cells:
        axis.scatter(
            [cell["longitude"] for cell in long_snap_cells], [cell["latitude"] for cell in long_snap_cells],
            marker="x", s=10, color="#111827", linewidths=0.6, label=f"Road snap > {max_snap_distance / 1000:g} km",
        )
    fig.colorbar(scatter, ax=axis, label="Walking + driving time to nearest facility (minutes)")
    axis.set(title=f"Health-facility road access — {district_name}", xlabel="Longitude", ylabel="Latitude", aspect="equal")
    min_x, min_y, max_x, max_y = boundary.bounds
    axis.set_xlim(min_x - 0.02, max_x + 0.02)
    axis.set_ylim(min_y - 0.02, max_y + 0.02)
    axis.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(OUTPUTS / f"{slug}-access.png", dpi=180)
    plt.close(fig)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", default="Dhaka")
    parser.add_argument("--osrm-url", default="http://127.0.0.1:5001")
    parser.add_argument("--threshold-minutes", type=float, default=120)
    parser.add_argument("--max-road-snap-m", type=float, default=2000)
    parser.add_argument("--walking-speed-kmh", type=float, default=3.0, help="Off-road first-mile approximation")
    parser.add_argument("--facility-buffer-degrees", type=float, default=0.25)
    parser.add_argument("--source-batch", type=int, default=150)
    parser.add_argument("--destination-batch", type=int, default=300)
    args = parser.parse_args()
    district_feature, district_geometry = load_district(args.district)
    cells = population_cells(district_geometry)
    facilities = facilities_near(district_geometry, args.facility_buffer_degrees)
    if not cells or not facilities:
        raise RuntimeError(f"Pilot requires population cells and facilities; found {len(cells)} and {len(facilities)}")
    print(f"Loaded {len(cells)} population cells and {len(facilities)} candidate facilities")
    compute_access(cells, facilities, args.osrm_url, args.source_batch, args.destination_batch, args.walking_speed_kmh)
    print(json.dumps(write_outputs(district_feature, args.district, cells, facilities, args.threshold_minutes, args.max_road_snap_m, args.walking_speed_kmh), indent=2))


if __name__ == "__main__":
    main()
