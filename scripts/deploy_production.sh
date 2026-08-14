#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.production ]]; then
  echo "Missing $ROOT/.env.production" >&2
  exit 1
fi

set -a
source .env.production
set +a

: "${ANDROID_HOME:?ANDROID_HOME is required}"
: "${SHASTHOPATH_KEYSTORE_PATH:?SHASTHOPATH_KEYSTORE_PATH is required}"
: "${SHASTHOPATH_KEYSTORE_PASSWORD:?SHASTHOPATH_KEYSTORE_PASSWORD is required}"
: "${SHASTHOPATH_KEY_PASSWORD:?SHASTHOPATH_KEY_PASSWORD is required}"
: "${SHASTHOPATH_ADMIN_TOKEN:?SHASTHOPATH_ADMIN_TOKEN is required}"

export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ROOT/.tools/node/bin:$ANDROID_HOME/platform-tools:$PATH"
export GRADLE_OPTS="-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8 -Dorg.gradle.daemon=false"

npm ci
npm run android:sync
(cd android && ./gradlew assembleRelease)

install -d web/downloads data/reports
install -m 0644 android/app/build/outputs/apk/release/app-release.apk web/downloads/shasthopath-1.1.1.apk
(cd web/downloads && sha256sum shasthopath-1.1.1.apk > shasthopath-1.1.1.apk.sha256)
APK_SHA256="$(sha256sum web/downloads/shasthopath-1.1.1.apk | awk '{print $1}')"
printf '{\n  "version": "1.1.1",\n  "version_code": 3,\n  "apk_url": "https://shasthopath.krrkhan.com/downloads/shasthopath-1.1.1.apk",\n  "sha256": "%s"\n}\n' "$APK_SHA256" > web/app-version.json

sudo chown -R 10001:10001 data/reports
sudo docker compose -f deploy/compose.production.yml build
sudo docker compose -f deploy/compose.production.yml up -d --remove-orphans
sudo docker compose -f deploy/compose.production.yml ps
