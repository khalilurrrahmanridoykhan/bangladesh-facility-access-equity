#!/usr/bin/env python3
"""Download and record the public inputs used by the access pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
HDX_API = "https://data.humdata.org/api/3/action/package_show"


def download(url: str, destination: Path) -> dict:
    if destination.exists() and destination.stat().st_size:
        return {"url": url, "path": str(destination.relative_to(ROOT)), "bytes": destination.stat().st_size, "cached": True}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    with requests.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with temporary.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
    temporary.replace(destination)
    return {"url": url, "path": str(destination.relative_to(ROOT)), "bytes": size, "sha256": digest.hexdigest(), "cached": False}


def hdx_resource(dataset: str, formats: tuple[str, ...], name_contains: str = "") -> tuple[str, dict]:
    response = requests.get(HDX_API, params={"id": dataset}, timeout=60)
    response.raise_for_status()
    package = response.json()["result"]
    candidates = [
        resource for resource in package["resources"]
        if resource.get("format", "").lower() in formats
        and name_contains.lower() in resource.get("name", "").lower()
    ]
    if not candidates:
        raise RuntimeError(f"No matching resource in HDX dataset {dataset}")
    resource = candidates[0]
    return resource.get("download_url") or resource["url"], {
        "dataset": dataset,
        "dataset_modified": package.get("metadata_modified"),
        "resource": resource.get("name"),
        "resource_modified": resource.get("last_modified"),
        "license": package.get("license_title"),
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {"sources": []}

    health_url, health_meta = hdx_resource("bangladesh-healthsites", ("geojson",), "hxl")
    health = download(health_url, RAW / "bangladesh_healthsites.geojson")
    manifest["sources"].append({**health_meta, **health})

    population_url, population_meta = hdx_resource(
        "worldpop-population-counts-for-bangladesh", ("geotiff",), "2020_1km_aggregated.tif"
    )
    population = download(population_url, RAW / "bgd_ppp_2020_1km_aggregated.tif")
    manifest["sources"].append({**population_meta, **population})

    boundaries_url = "https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/gbOpen/BGD/ADM2/geoBoundaries-BGD-ADM2.geojson"
    boundaries = download(boundaries_url, RAW / "geoBoundaries-BGD-ADM2.geojson")
    manifest["sources"].append({"dataset": "geoBoundaries BGD ADM2", "license": "CC BY 4.0", **boundaries})

    osm_url = "https://download.geofabrik.de/asia/bangladesh-latest.osm.pbf"
    osm = download(osm_url, RAW / "bangladesh-latest.osm.pbf")
    manifest["sources"].append({"dataset": "Geofabrik Bangladesh OpenStreetMap extract", "license": "ODbL", **osm})

    (RAW / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

