#!/usr/bin/env python3
"""Serve the public PWA and accept minimal, privacy-conscious facility reports."""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ALLOWED_ISSUES = {"location", "closed", "name", "other"}
ALLOWED_DISTRICTS = {"Dhaka", "Bandarban"}
MAX_BODY_BYTES = 16_384


class AppHandler(SimpleHTTPRequestHandler):
    report_file = ROOT / "data" / "reports" / "facility-reports.ndjson"
    write_lock = threading.Lock()
    requests_by_client: dict[str, deque[float]] = defaultdict(deque)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "geolocation=(self)")
        super().end_headers()

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/api/health":
            self.send_json(HTTPStatus.OK, {"status": "ok", "service": "shasthopath-feedback"})
            return
        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/reports":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self.within_rate_limit():
            self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid_body_size"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            report = self.validate_report(payload)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_report", "detail": str(error)})
            return
        self.report_file.parent.mkdir(parents=True, exist_ok=True)
        with self.write_lock, self.report_file.open("a", encoding="utf-8") as output:
            output.write(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.send_json(HTTPStatus.CREATED, {"id": report["id"], "status": report["status"]})

    def within_rate_limit(self) -> bool:
        key = self.client_address[0]
        now = time.monotonic()
        recent = self.requests_by_client[key]
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 10:
            return False
        recent.append(now)
        return True

    @staticmethod
    def validate_report(payload: dict) -> dict:
        facility_wrapper = payload.get("facility")
        if not isinstance(facility_wrapper, dict):
            raise ValueError("facility must be an object")
        district = facility_wrapper.get("district")
        facility = facility_wrapper.get("facility")
        issue = payload.get("issue")
        note = str(payload.get("note", "")).strip()
        if district not in ALLOWED_DISTRICTS:
            raise ValueError("unsupported district")
        if not isinstance(facility, list) or len(facility) != 4:
            raise ValueError("facility must contain longitude, latitude, name and type")
        longitude, latitude, name, facility_type = facility
        if not (-180 <= float(longitude) <= 180 and -90 <= float(latitude) <= 90):
            raise ValueError("invalid facility coordinates")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("invalid facility name")
        if not isinstance(facility_type, str) or len(facility_type) > 100:
            raise ValueError("invalid facility type")
        if issue not in ALLOWED_ISSUES:
            raise ValueError("unsupported issue")
        if not 3 <= len(note) <= 500:
            raise ValueError("note must be 3 to 500 characters")
        return {
            "id": str(uuid.uuid4()), "status": "new", "received_at": datetime.now(timezone.utc).isoformat(),
            "district": district, "facility": facility, "issue": issue, "note": note,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--report-file", type=Path, default=AppHandler.report_file)
    args = parser.parse_args()
    AppHandler.report_file = args.report_file
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"ShasthoPath running at http://{args.host}:{args.port}")
    print(f"Facility reports: {args.report_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
