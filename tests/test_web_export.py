import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicWebDataTests(unittest.TestCase):
    def test_exported_pilots_match_public_schema(self):
        for district in ("dhaka", "bandarban"):
            payload = json.loads((ROOT / "web" / "data" / f"{district}.json").read_text())
            self.assertEqual(payload["schema"], "facility-access-public-v1")
            self.assertGreater(len(payload["cells"]), 100)
            self.assertGreater(len(payload["facilities"]), 10)
            self.assertEqual(len(payload["cell_fields"]), len(payload["cells"][0]))
            self.assertEqual(len(payload["facility_fields"]), len(payload["facilities"][0]))
            self.assertEqual(payload["summary"]["district"].casefold(), district)

    def test_national_catalog_has_all_districts_and_data_files(self):
        catalog = json.loads((ROOT / "web" / "data" / "catalog.json").read_text())
        self.assertEqual(catalog["national"]["districts"], 64)
        self.assertEqual(len(catalog["districts"]), 64)
        self.assertGreater(catalog["national"]["population_over_threshold"], 0)
        for district in catalog["districts"]:
            self.assertTrue(district["name_bn"])
            self.assertTrue((ROOT / "web" / "data" / f"{district['slug']}.json").exists())

    def test_national_overview_has_all_district_geometries(self):
        path = ROOT / "web" / "data" / "national.json"
        payload = json.loads(path.read_text())
        self.assertEqual(payload["schema"], "facility-access-national-v1")
        self.assertEqual(payload["summary"]["districts"], 64)
        self.assertEqual(len(payload["districts"]["features"]), 64)
        self.assertLess(path.stat().st_size, 5_000_000)
        self.assertTrue(all(feature["properties"]["name_bn"] for feature in payload["districts"]["features"]))

    def test_public_app_defaults_to_clickable_national_overview(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn('?requested:"national"', javascript)
        self.assertIn('facility-access-national-v1', javascript)
        self.assertIn('window.selectDistrict=setDistrict', javascript)

    def test_facility_directory_supports_filters_and_shareable_links(self):
        html = (ROOT / "web" / "index.html").read_text()
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn('id="facilityType"', html)
        self.assertIn('id="facilityDirectory"', html)
        self.assertIn("renderFacilityDirectory", javascript)
        self.assertIn('url.searchParams.set("facility",index)', javascript)
        self.assertIn("navigator.share", javascript)

    def test_district_data_and_tiles_can_be_saved_offline(self):
        html = (ROOT / "web" / "index.html").read_text()
        javascript = (ROOT / "web" / "app.js").read_text()
        service_worker = (ROOT / "web" / "service-worker.js").read_text()
        self.assertIn('id="offlineDownload"', html)
        self.assertIn('OFFLINE_CACHE="shasthopath-districts-v1"', javascript)
        self.assertIn("for(let zoom=8;zoom<=11;zoom++)", javascript)
        self.assertIn("cacheOfflineDistrict", javascript)
        self.assertIn('hostname.endsWith("basemaps.cartocdn.com")', service_worker)

    def test_pwa_core_assets_exist(self):
        for name in ("index.html", "download.html", "app.js", "styles.css", "directory.css", "app-download.css", "manifest.webmanifest", "service-worker.js", "icon.svg", "tile-fallback.svg"):
            self.assertGreater((ROOT / "web" / name).stat().st_size, 0)

    def test_android_download_page_and_live_api_bridge_exist(self):
        download = (ROOT / "web" / "download.html").read_text()
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn("downloads/shasthopath-1.2.1.apk", download)
        self.assertIn("https://shasthopath.krrkhan.com", javascript)

    def test_android_sync_excludes_hosted_apk_downloads(self):
        sync_script = (ROOT / "scripts" / "sync_android.sh").read_text()
        package = json.loads((ROOT / "package.json").read_text())
        self.assertIn("--exclude 'downloads/'", sync_script)
        self.assertEqual(package["scripts"]["android:sync"], "bash scripts/sync_android.sh")

    def test_mobile_navigation_and_native_location_are_present(self):
        html = (ROOT / "web" / "index.html").read_text()
        javascript = (ROOT / "web" / "app.js").read_text()
        styles = (ROOT / "web" / "styles.css").read_text()
        manifest = (ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
        package = (ROOT / "package.json").read_text()
        self.assertIn('id="mobileNav"', html)
        self.assertIn('data-mobile-action="near"', html)
        self.assertNotIn('data-mobile-action="app"', html)
        self.assertIn('class="brand-mark brand-link" href="update.html"', html)
        self.assertIn("nativeGeolocation", javascript)
        self.assertIn("requestPermissions", javascript)
        self.assertIn("scrollIntoView", javascript)
        self.assertIn("selectNationalArea", javascript)
        self.assertIn("focusUserLocation", javascript)
        self.assertIn("userAccuracyLayer.getBounds", javascript)
        self.assertIn('id="districtDialog"', html)
        self.assertIn('id="districtSearch"', html)
        self.assertIn("renderDistrictOptions", javascript)
        self.assertIn('id="facilityPagination"', html)
        self.assertIn("PAGE_SIZE=20", javascript)
        self.assertIn('id="welcomeScreen"', html)
        self.assertIn("showWelcome", javascript)
        self.assertIn(".mobile-nav", styles)
        self.assertIn(".leaflet-interactive:focus{outline:none}", styles)
        self.assertIn("ACCESS_FINE_LOCATION", manifest)
        self.assertIn("@capacitor/geolocation", package)
        self.assertIn("`${API_BASE}/api/reports`", javascript)

    def test_in_app_update_center_and_signed_installer_are_present(self):
        update_html = (ROOT / "web" / "update.html").read_text()
        update_js = (ROOT / "web" / "update.js").read_text()
        version = json.loads((ROOT / "web" / "app-version.json").read_text())
        updater = (ROOT / "android" / "app" / "src" / "main" / "java" / "org" / "shasthopath" / "app" / "AppUpdaterPlugin.java").read_text()
        manifest = (ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
        self.assertIn('id="updateNow"', update_html)
        self.assertIn('class="back-link" href="index.html"', update_html)
        self.assertIn("AppUpdater", update_js)
        self.assertEqual(version["version"], "1.2.1")
        self.assertRegex(version["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn('UPDATE_HOST = "shasthopath.krrkhan.com"', updater)
        self.assertIn("hasMatchingSigner", updater)
        self.assertIn("The update checksum does not match", updater)
        self.assertIn("REQUEST_INSTALL_PACKAGES", manifest)
        self.assertIn("Khalilur Rahman Ridoy Khan", update_html)
        self.assertIn("https://krrkhan.com", update_html)

    def test_public_app_avoids_inline_handlers_for_strict_csp(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertNotIn("onclick=", javascript)
        self.assertIn('map.on("popupopen"', javascript)

    def test_feedback_dialog_and_directions_are_present(self):
        html = (ROOT / "web" / "index.html").read_text()
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn('id="reportDialog"', html)
        self.assertIn("shasthopath-reports", javascript)
        self.assertIn("google.com/maps/dir", javascript)
        self.assertIn('/api/reports', javascript)
        self.assertIn('id="closeReport"', html)
        self.assertIn('id="cancelReport"', html)
        self.assertIn('document.querySelector("#closeReport").addEventListener', javascript)

    def test_leaflet_is_served_locally(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn("vendor/leaflet/leaflet.css", html)
        self.assertIn("vendor/leaflet/leaflet.js", html)
        self.assertNotIn("unpkg.com/leaflet", html)
        self.assertGreater((ROOT / "web" / "vendor" / "leaflet" / "leaflet.css").stat().st_size, 10_000)

    def test_admin_dashboard_assets_exist(self):
        for name in ("admin.html", "admin.css", "admin.js"):
            self.assertGreater((ROOT / "web" / name).stat().st_size, 100)
        self.assertIn("/api/admin/reports", (ROOT / "web" / "admin.js").read_text())
        self.assertIn('pathname.startsWith("/api/")', (ROOT / "web" / "service-worker.js").read_text())


if __name__ == "__main__":
    unittest.main()
