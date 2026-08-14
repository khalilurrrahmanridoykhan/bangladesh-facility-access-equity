# Legacy union-level analysis

This directory preserves the repository's original national union-level pipeline and result. It computes OSRM car travel from each populated 1 km WorldPop grid cell to one of eight straight-line-nearest candidates from a deduplicated union of LGED and Healthsites facilities.

The original run reported 222,225 people (0.13% of approximately 164.7 million raster-modeled residents) as either more than two hours from a facility by road or without a mapped road route. City Corporation cells are included in the national total but cannot be assigned to Union polygons.

These figures use a different methodology and facility dataset from the current ShasthoPath model. They are retained for reproducibility and must not be presented as equivalent to the current model's results.

## Preserved pipeline

```text
scripts/01_fetch_data.py
scripts/02_build_osrm_graph.sh
scripts/03_prepare_facilities.py
scripts/04_prepare_population_grid.py
scripts/05_compute_travel_times.py
scripts/06_aggregate_by_union.py
```

The published output is [data/output/union_access_summary.csv](data/output/union_access_summary.csv). The associated pure-logic tests are also preserved under `tests/`.

## Original data choices

- Geofabrik Bangladesh OpenStreetMap road extract
- LGED facilities plus Bangladesh Healthsites, deduplicated
- WorldPop Bangladesh 2020 population counts at 1 km resolution
- Union boundaries previously validated by the related Bangladesh geo service

Known simplifications include a car-only routing profile, no traffic or seasonal road closures, a 1 km population grid, an eight-facility candidate prefilter, and incomplete mapped facility coverage.

## License

Code is MIT. Underlying facility, population, boundary, and road data retain their respective third-party licenses.
