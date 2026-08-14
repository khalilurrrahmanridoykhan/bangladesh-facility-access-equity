#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/shasthopath-capacitor.XXXXXX")"

if [[ ! -d "$STAGING_DIR" || "$(basename "$STAGING_DIR")" != shasthopath-capacitor.* ]]; then
  echo "Unable to create a safe Android web staging directory" >&2
  exit 1
fi

rsync -a --exclude 'downloads/' "$ROOT/web/" "$STAGING_DIR/"
cd "$ROOT"
CAPACITOR_WEB_DIR="$STAGING_DIR" npx cap sync android
