#!/usr/bin/env bash
# Builds the routable OSRM graph from the Bangladesh road network extract,
# using the car profile (a deliberate, documented scope choice -- see
# README) and the MLD pipeline (extract -> partition -> customize), which
# is the faster option for the many one-to-many /table queries this
# project runs, versus the older CH (contraction hierarchies) pipeline.
set -euo pipefail

cd "$(dirname "$0")/.."

RAW="data/raw/bangladesh.osm.pbf"
CAR_PROFILE="$(brew --prefix osrm-backend)/share/osrm/profiles/car.lua"

if [ ! -f "$RAW" ]; then
  echo "Missing $RAW -- run scripts/01_fetch_data.py first." >&2
  exit 1
fi

echo "== osrm-extract =="
osrm-extract -p "$CAR_PROFILE" "$RAW"

echo "== osrm-partition =="
osrm-partition "data/raw/bangladesh.osrm"

echo "== osrm-customize =="
osrm-customize "data/raw/bangladesh.osrm"

echo "Graph ready: data/raw/bangladesh.osrm"
echo "Start the routing server with:"
echo "  osrm-routed --algorithm mld --max-table-size 2000 --port 5050 data/raw/bangladesh.osrm"
echo "(port 5050, not the OSRM default 5000, since that's often taken by macOS AirPlay Receiver)"
