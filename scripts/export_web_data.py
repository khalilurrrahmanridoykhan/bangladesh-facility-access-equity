#!/usr/bin/env python3
"""Create compact, public-facing pilot datasets for the static PWA."""

from __future__ import annotations

import csv
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_pilot import facilities_near, load_district, slugify

DISTRICT_NAMES_BN = {
    "Bagerhat": "বাগেরহাট", "Bandarban": "বান্দরবান", "Barguna": "বরগুনা", "Barisal": "বরিশাল",
    "Bhola": "ভোলা", "Bogra": "বগুড়া", "Brahamanbaria": "ব্রাহ্মণবাড়িয়া", "Chandpur": "চাঁদপুর",
    "Chittagong": "চট্টগ্রাম", "Chuadanga": "চুয়াডাঙ্গা", "Comilla": "কুমিল্লা", "Cox's Bazar": "কক্সবাজার",
    "Dhaka": "ঢাকা", "Dinajpur": "দিনাজপুর", "Faridpur": "ফরিদপুর", "Feni": "ফেনী",
    "Gaibandha": "গাইবান্ধা", "Gazipur": "গাজীপুর", "Gopalganj": "গোপালগঞ্জ", "Habiganj": "হবিগঞ্জ",
    "Jamalpur": "জামালপুর", "Jessore": "যশোর", "Jhalokati": "ঝালকাঠি", "Jhenaidah": "ঝিনাইদহ",
    "Joypurhat": "জয়পুরহাট", "Khagrachhari": "খাগড়াছড়ি", "Khulna": "খুলনা", "Kishoreganj": "কিশোরগঞ্জ",
    "Kurigram": "কুড়িগ্রাম", "Kushtia": "কুষ্টিয়া", "Lakshmipur": "লক্ষ্মীপুর", "Lalmonirhat": "লালমনিরহাট",
    "Madaripur": "মাদারীপুর", "Magura": "মাগুরা", "Manikganj": "মানিকগঞ্জ", "Maulvibazar": "মৌলভীবাজার",
    "Meherpur": "মেহেরপুর", "Munshiganj": "মুন্সিগঞ্জ", "Mymensingh": "ময়মনসিংহ", "Naogaon": "নওগাঁ",
    "Narail": "নড়াইল", "Narayanganj": "নারায়ণগঞ্জ", "Narsingdi": "নরসিংদী", "Natore": "নাটোর",
    "Nawabganj": "চাঁপাইনবাবগঞ্জ", "Netrakona": "নেত্রকোনা", "Nilphamari": "নীলফামারী", "Noakhali": "নোয়াখালী",
    "Pabna": "পাবনা", "Panchagarh": "পঞ্চগড়", "Patuakhali": "পটুয়াখালী", "Pirojpur": "পিরোজপুর",
    "Rajbari": "রাজবাড়ী", "Rajshahi": "রাজশাহী", "Rangamati": "রাঙামাটি", "Rangpur": "রংপুর",
    "Satkhira": "সাতক্ষীরা", "Shariatpur": "শরীয়তপুর", "Sherpur": "শেরপুর", "Sirajganj": "সিরাজগঞ্জ",
    "Sunamganj": "সুনামগঞ্জ", "Sylhet": "সিলেট", "Tangail": "টাঙ্গাইল", "Thakurgaon": "ঠাকুরগাঁও",
}


def export(district: str) -> dict:
    slug = slugify(district)
    legacy_slug = district.casefold().replace(" ", "-")
    summary_path = ROOT / "outputs" / f"{slug}-summary.json"
    cells_path = ROOT / "outputs" / f"{slug}-access.csv"
    if not summary_path.exists() and legacy_slug != slug:
        summary_path = ROOT / "outputs" / f"{legacy_slug}-summary.json"
        cells_path = ROOT / "outputs" / f"{legacy_slug}-access.csv"
    if not summary_path.exists() or not cells_path.exists():
        raise FileNotFoundError(f"Run the {district} pilot before exporting web data")

    feature, geometry = load_district(district)
    facilities = facilities_near(geometry, 0.25)
    cells = []
    with cells_path.open() as source:
        for row in csv.DictReader(source):
            access_minutes = row["total_access_time_minutes"]
            cells.append([
                round(float(row["longitude"]), 5), round(float(row["latitude"]), 5),
                round(float(row["population"])), round(float(access_minutes), 1) if access_minutes else None,
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
    return {
        "slug": slug, "name": district, "name_bn": DISTRICT_NAMES_BN.get(district, district), "population": payload["summary"]["estimated_population"],
        "population_over_threshold": payload["summary"]["population_over_threshold"],
        "percent_over_threshold": payload["summary"]["percent_population_over_threshold"],
        "facilities": len(public_facilities),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("district", nargs="*", help="District names; defaults to every completed output")
    args = parser.parse_args()
    if args.district:
        names = args.district
    else:
        names = sorted(
            json.loads(path.read_text())["district"]
            for path in (ROOT / "outputs").glob("*-summary.json")
        )
    if not names:
        raise SystemExit("No completed district summaries found")
    catalog = [export(name) for name in names]
    destination = ROOT / "web" / "data" / "catalog.json"
    total_population = sum(item["population"] for item in catalog)
    total_over = sum(item["population_over_threshold"] for item in catalog)
    national = {
        "districts": len(catalog), "estimated_population": total_population,
        "population_over_threshold": total_over,
        "percent_over_threshold": round(100 * total_over / total_population, 3) if total_population else None,
    }
    destination.write_text(json.dumps({"national": national, "districts": catalog}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {destination.relative_to(ROOT)} with {len(catalog)} districts")
