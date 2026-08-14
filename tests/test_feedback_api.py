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
        AppHandler.report_file = cls.report_file
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


if __name__ == "__main__":
    unittest.main()
