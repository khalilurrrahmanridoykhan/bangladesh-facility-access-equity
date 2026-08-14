"""
Downloads the four real, public datasets this pipeline needs into data/raw/.
Every URL here was verified live (HTTP HEAD / HDX CKAN API) before being
hardcoded -- see the project README for how each was confirmed.
"""

import sys
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

SOURCES = {
    # Road network -- Geofabrik's Bangladesh extract. The "-latest" URL
    # 302-redirects to a dated file; requests follows redirects by default.
    "bangladesh.osm.pbf": "https://download.geofabrik.de/asia/bangladesh-latest.osm.pbf",
    # Health facilities, primary source: Local Government Engineering
    # Department (LGED), via HDX (updated by WFP/MapAction/OCHA).
    "lged_facilities.zip": (
        "https://data.humdata.org/dataset/80920682-bbb5-421e-b7ac-f89b7b640a5c/"
        "resource/c545d196-bc2c-44ed-9028-316ab080a41c/download/bgd_poi_healthfacilities_lged.zip"
    ),
    # Health facilities, cross-check source: Global Healthsites Mapping
    # Project (OSM-sourced), used only to quantify LGED's coverage gap.
    "healthsites.geojson": (
        "https://data.humdata.org/dataset/ab89f238-af45-419e-94aa-f91ef0ce42d0/"
        "resource/51170838-b2f0-4388-94a2-8f72f157e312/download/bangladesh_hxl.geojson"
    ),
    # Population, WorldPop 2020, 1km resolution, UN-adjusted, aggregated.
    # Deliberately the 1km product (~850KB) not the 100m product (~75-80MB)
    # -- keeps the populated-cell grid tractable for a v1 build.
    "population_2020_1km.tif": (
        "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/"
        "2020/BGD/bgd_ppp_2020_1km_Aggregated_UNadj.tif"
    ),
}


def download(name: str, url: str) -> None:
    dest = RAW_DIR / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip (already present): {name} ({dest.stat().st_size:,} bytes)")
        return

    print(f"fetching {name} <- {url}")
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        written = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                written += len(chunk)
                if total:
                    print(f"\r  {written:,} / {total:,} bytes", end="", flush=True)
        print()
    print(f"  done: {dest} ({dest.stat().st_size:,} bytes)")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        download(name, url)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
