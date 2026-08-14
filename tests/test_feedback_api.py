import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from serve_app import AppHandler, ThreadingHTTPServer


class FeedbackApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.report_file = Path(cls.temporary.name) / "reports.ndjson"
        cls.status_file = Path(cls.temporary.name) / "status.ndjson"
        AppHandler.report_file = cls.report_file
        AppHandler.status_file = cls.status_file
        AppHandler.admin_token = "test-admin-token"
        AppHandler.requests_by_client.clear()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temporary.cleanup()

    def post(self, payload):
        request = Request(
            self.base_url + "/api/reports", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(request) as response:
            return response.status, json.load(response)

    def test_health_endpoint(self):
        with urlopen(self.base_url + "/api/health") as response:
            self.assertEqual(json.load(response)["status"], "ok")

    def test_native_app_origin_can_preflight_feedback_api(self):
        request = Request(
            self.base_url + "/api/reports",
            headers={"Origin": "https://localhost", "Access-Control-Request-Method": "POST"},
            method="OPTIONS",
        )
        with urlopen(request) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://localhost")
            self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])

    def test_unknown_origin_cannot_preflight_feedback_api(self):
        request = Request(self.base_url + "/api/reports", headers={"Origin": "https://example.com"}, method="OPTIONS")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_admin_requires_token_and_records_status_audit(self):
        payload = {
            "facility": {"district": "Bandarban", "facility": [92.2, 22.1, "Review Hospital", "hospital"]},
            "issue": "closed", "note": "The facility appeared closed during a visit.",
        }
        _, created = self.post(payload)
        with self.assertRaises(HTTPError) as unauthorized:
            urlopen(self.base_url + "/api/admin/reports")
        self.assertEqual(unauthorized.exception.code, 401)

        headers = {"Authorization": "Bearer test-admin-token"}
        with urlopen(Request(self.base_url + "/api/admin/reports", headers=headers)) as response:
            reports = json.load(response)["reports"]
        self.assertTrue(any(report["id"] == created["id"] for report in reports))

        review = Request(
            self.base_url + f"/api/admin/reports/{created['id']}",
            data=json.dumps({"status": "investigating", "review_note": "Checking with district office."}).encode(),
            headers={**headers, "Content-Type": "application/json"}, method="PATCH",
        )
        with urlopen(review) as response:
            result = json.load(response)
        self.assertEqual(result["status"], "investigating")
        audit = json.loads(self.status_file.read_text().splitlines()[-1])
        self.assertEqual(audit["report_id"], created["id"])
        self.assertEqual(audit["status"], "investigating")

    def test_valid_report_is_persisted_without_client_address(self):
        payload = {
            "facility": {"district": "Dhaka", "facility": [90.4, 23.8, "Test Hospital", "hospital"]},
            "issue": "location", "note": "The marker should be farther east.",
        }
        status, result = self.post(payload)
        self.assertEqual(status, 201)
        self.assertEqual(result["status"], "new")
        stored = json.loads(self.report_file.read_text().splitlines()[-1])
        self.assertEqual(stored["note"], payload["note"])
        self.assertNotIn("ip", stored)
        self.assertNotIn("client", stored)

    def test_invalid_report_is_rejected(self):
        payload = {"facility": {"district": "Dhaka", "facility": [90.4, 23.8, "X", "hospital"]}, "issue": "bad", "note": "ok note"}
        with self.assertRaises(HTTPError) as caught:
            self.post(payload)
        self.assertEqual(caught.exception.code, 400)

    def test_national_catalog_district_is_accepted(self):
        payload = {
            "facility": {"district": "Rangamati", "facility": [92.2, 22.7, "Hill Hospital", "hospital"]},
            "issue": "name", "note": "Facility name needs local verification.",
        }
        status, _ = self.post(payload)
        self.assertEqual(status, 201)


if __name__ == "__main__":
    unittest.main()
