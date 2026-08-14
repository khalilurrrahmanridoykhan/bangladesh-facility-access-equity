# Bangladesh Facility-Access Equity Tool

How much of Bangladesh's population is more than 2 hours by road from the
nearest health facility? A real answer, computed from real road-network
routing (OSRM) and real population/facility data -- not a straight-line
distance proxy dressed up as an access metric.

Not a DHIS2 app, not ODK/XLSForm -- a deliberate change of shape from the
rest of this developer's recent work, and a genuinely different toolchain
(Python + a self-hosted routing engine) to match.

## What this computes

For every ~1km populated grid cell in Bangladesh, the real road-network
travel time (via a locally-run OSRM instance) to the nearest health
facility, then aggregated to: what share of each Union's population is
more than 2 hours away, and nationally.

## Real data sources, every one verified live before use

| Data | Source | Notes |
|---|---|---|
| Road network | [Geofabrik](https://download.geofabrik.de/asia/bangladesh-latest.osm.pbf) | OSM extract, ~352MB, used to build the OSRM routing graph. |
| Health facilities | [HDX: Bangladesh - Health facilities by LGED](https://data.humdata.org/dataset/bangladesh-health-facilities-by-lged) + [HDX: Bangladesh Healthsites](https://data.humdata.org/dataset/bangladesh-healthsites) | See "A real finding" below for why both are used, not just the government list. |
| Population | [WorldPop Bangladesh 2020, 1km, UN-adjusted](https://data.humdata.org/dataset/worldpop-population-counts-for-bangladesh) | CC BY 4.0. 1km chosen over the 100m product specifically to keep the grid tractable. |
| Union boundaries | Reused from [`bangladesh-geo-service`](https://github.com/khalilurrrahmanridoykhan/onehealth-platform/tree/main/bangladesh-geo-service) | Already validated, already has the duplicate-`GEO_CODE` dissolve fix applied -- no reason to re-derive this a third time. |

## A real finding that changed the approach mid-build

The plan was to use the LGED (government, Local Government Engineering
Department) facility list as the primary source, with the crowd-sourced
Healthsites (OSM) list as a lightweight cross-check. Once both were loaded:

- LGED: 2,452 facilities (cleaned)
- Healthsites: 7,318 facilities (cleaned)
- **Only 18.9%** of Healthsites facilities had an LGED match within 1km

That gap was too large to treat LGED as sufficient on its own -- doing so
would have systematically overstated how underserved many areas are, since
it would miss the large majority of mapped facilities (mostly smaller
clinics and pharmacies LGED's registry doesn't cover). The pipeline uses
the **union of both sources, deduplicated** (9,408 facilities) instead.
This is documented here rather than quietly decided, because it's exactly
the kind of assumption that's easy to get wrong silently.

**The honest caveat that remains**: even the merged list reflects what's
been *mapped*, not a guaranteed-complete national facility registry.
Neither source claims to be exhaustive.

## Real results

National: **222,225 people (0.13%)** of Bangladesh's ~164.7M raster-modeled
population are either more than 2 hours from the nearest health facility by
road, or have no route to any facility at all on the mapped road network.

That low national number is expected -- Bangladesh is densely populated
with a fairly extensive rural road network. The real signal is in *where*
the gap concentrates. At the district level (unions only -- see the
City Corporation note below), every single district with a meaningfully
elevated underserved rate is an independently, well-documented remote part
of Bangladesh:

| District | Why this is a real, known-remote area |
|---|---|
| **Kurigram** | Brahmaputra river char (river-island) communities -- one of Bangladesh's most chronically remote and historically food-insecure districts. 6 of the top 10 most-underserved unions nationally are here (up to 92.1% of one union's population >2hr from care). |
| **Chapainawabganj, Rajbari** | Padma river char communities (Goalanda/Daulatdia's char settlements are well documented). |
| **Satkhira, Patuakhali** | Coastal, Sundarbans-adjacent and river-delta char areas in the south. |
| **Habiganj, Sunamganj** | The Sylhet Basin's haor (seasonal wetland) belt -- exactly the kind of terrain this pipeline's plan flagged as a real plausibility target before any result existed. |
| **Rangamati** | Chittagong Hill Tracts -- genuinely difficult hilly terrain. |

Not one unexpected/implausible district appears in the elevated group --
this is the real validation pass this project's plan called for, and it
passed.

**A real finding from the aggregation step itself**: 4,625 population cells
(~24.4M people) fell outside every Union polygon during the spatial join.
Investigating *why* rather than just excluding them found they cluster
tightly around central Dhaka's real coordinates -- not a bug, but a real
fact about Bangladesh's administrative structure: City Corporations (Dhaka,
Chattogram, etc.) are subdivided into **Wards**, not **Unions**, so they're
legitimately absent from Union boundary data. The national total above is
computed over *all* cells for this reason; the district/union breakdown
necessarily excludes City Corporation areas.

Full results: [`data/output/union_access_summary.csv`](data/output/union_access_summary.csv).

## Pipeline

```
scripts/
  01_fetch_data.py            # downloads the 4 real datasets into data/raw/
  02_build_osrm_graph.sh      # osrm-extract -> osrm-partition -> osrm-customize
  03_prepare_facilities.py    # clean + merge LGED and Healthsites, report the coverage-gap check
  04_prepare_population_grid.py  # rasterio: populated cells from the WorldPop raster
  05_compute_travel_times.py     # for each cell: real OSRM travel time to the nearest facility
  06_aggregate_by_union.py       # spatial join to Union polygons, aggregate underserved population
```

```bash
pip install -r requirements.txt
brew install osrm-backend   # bottled/pre-built, no Docker needed

python scripts/01_fetch_data.py
bash scripts/02_build_osrm_graph.sh
osrm-routed --algorithm mld --max-table-size 2000 --port 5050 data/raw/bangladesh.osrm &

python scripts/03_prepare_facilities.py
python scripts/04_prepare_population_grid.py
python scripts/05_compute_travel_times.py     # add --bbox for a small-area test run first
python scripts/06_aggregate_by_union.py
```

## Known simplifications, stated plainly

- **Car profile only.** This measures vehicle/ambulance-reachable access,
  not walking or boat access -- a real gap for Bangladesh's many river/char
  communities, some of which are genuinely not connected to the mapped
  road network at all (see `no_road_connection` in the output, treated as
  underserved rather than silently dropped).
- **No traffic, flooding, or seasonal road-closure modeling.** OSRM's graph
  reflects the mapped road network's structure and speed limits, not
  real-world conditions on any given day.
- **1km population grid**, not the 100m product -- a real resolution
  tradeoff made to keep the routing step tractable for a v1 build.
- **Straight-line candidate prefiltering.** Each cell only gets routed
  against its 8 straight-line-nearest facilities, not all ~9,400 nationwide
  -- keeps each OSRM query small. The actual travel time used is always
  OSRM's real road-network result, never the straight-line distance itself;
  this only affects which facilities get considered as candidates.
- **Facility list is what's mapped**, not a guaranteed-complete registry --
  see "A real finding" above.

## Verification performed

- Population raster sanity check: cells sum to ~164.7M, within a plausible
  range of Bangladesh's real population (~170M).
- OSRM sanity check: a manual test route inside Dhaka returned a real,
  plausible travel time before any bulk computation was trusted.
- Small-scale validation (Barishal division bbox, ~11,600 cells) run and
  inspected for real variance (0-71 min, not artificially flat) before
  scaling to the full national run.
- `pytest` covers the pure-logic pieces (facility cleaning/merging,
  geoshape parsing, underserved classification and aggregation math)
  against small hand-built fixtures -- no network or OSRM dependency in
  the test suite itself.

## License

Code is MIT. Underlying facility, population, and road-network data each
carry their own third-party license terms (ODbL, CC BY 4.0, and OSM's own
license respectively) -- see each source's own page linked above before
reusing the *data* outside this project.
