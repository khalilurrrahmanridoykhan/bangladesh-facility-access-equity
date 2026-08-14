#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h:h}"
PBF="$PROJECT_DIR/data/raw/bangladesh-latest.osm.pbf"
GRAPH="${PBF%.osm.pbf}.osrm"
PROFILE="$(brew --prefix osrm-backend)/share/osrm/profiles/car.lua"

if [[ ! -s "$PBF" ]]; then
  print -u2 "Missing $PBF; run 'make download' first."
  exit 1
fi
if [[ ! -f "$PROFILE" ]]; then
  print -u2 "OSRM car profile not found at $PROFILE"
  exit 1
fi

if [[ ! -s "$GRAPH.ebg" ]]; then
  osrm-extract -p "$PROFILE" "$PBF"
fi
osrm-partition "$GRAPH"
osrm-customize "$GRAPH"
