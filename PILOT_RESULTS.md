# Pilot results

## Dhaka

- Population cells: 1,855
- Estimated 2020 population: 15,981,221
- Candidate facilities: 1,004
- Population-weighted driving time: 3.25 minutes
- Population-weighted combined access time: 4.45 minutes
- Population over 120 combined minutes: 0
- Population represented by cell centres snapped more than 2 km to a road: 6,209 (0.039%)

The road-only result is suitable for continued technical validation because nearly all represented population is close to the routable road network.

## Bandarban

- Population cells: 5,749
- Estimated 2020 population: 536,748
- Candidate facilities: 97
- Population-weighted driving time: 20.35 minutes
- Population-weighted combined access time: 51.28 minutes
- Population over 120 combined minutes: 47,266 (8.806%)
- Population represented by cell centres snapped more than 2 km to a road: 123,622 (23.032%)
- Maximum road snap: 28.64 km

The combined model adds a conservative straight-line walking approximation at 3 km/h for the population-to-road and road-to-facility snap segments. It identifies about 47,266 people beyond the two-hour threshold. Almost half of the raster cells, representing about 23% of estimated population, still have a road snap over 2 km; terrain and trail routing must be field-validated before interpreting these figures as precise journey times.

## Decision

The documented walking approximation is suitable for a national screening layer if its uncertainty remains visible. Before public decision support, replace or calibrate straight-line walking with a walking/trail and terrain model, then validate sampled routes with local partners. Continue reporting walking and driving components separately.
