# Bangladesh Facility-Access Equity Pilot

This pilot estimates combined first-mile walking and road travel time from populated 1 km cells to the nearest mapped health facility. Cells whose nearest reachable facility is more than 120 minutes away are flagged as underserved.

## Data

- Health facilities: HDX Bangladesh Healthsites (ODbL)
- Population: WorldPop 2020 population counts, 1 km aggregate
- Roads: Geofabrik Bangladesh OpenStreetMap extract (ODbL)
- Pilot boundary: geoBoundaries Bangladesh ADM2 (CC BY 4.0)

Downloaded data and generated OSRM files are excluded from Git. `data/raw/source-manifest.json` records the exact resolved resources and download metadata.

## Run

```bash
make setup
make download
make graph
osrm-routed --algorithm mld --ip 127.0.0.1 --port 5001 --max-table-size 500 data/raw/bangladesh-latest.osrm
make pilot
```

The pilot writes GeoJSON, CSV, a PNG map, and a JSON summary into `outputs/`.

## Method

Population raster cell centres with positive population are clipped to the selected district. Facilities are clipped to the district plus a configurable buffer, snapped by OSRM, and evaluated in batches with OSRM's Table API. The minimum driving duration is retained for each cell. Unreachable cells remain explicit rather than being treated as greater than two hours.

OSRM's distance from each population-cell centre to its snapped road location is retained as `road_snap_distance_m`. The model converts the population and facility road-snap distances to walking time at a conservative default speed of 3 km/h, then adds this to OSRM driving time. Cells farther than 2 km from a drivable road are also marked `long_road_snap` because straight-line walking remains an approximation, especially in mountainous terrain.

This is a screening tool. Healthsites completeness and OSM road coverage must be validated before policy use.
