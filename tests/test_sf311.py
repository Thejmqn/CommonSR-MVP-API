import json
import os
import unittest
from unittest.mock import patch

from requests import Response
from requests.exceptions import HTTPError, RequestException

from sf311 import fetch_latest_requests


class FetchLatestRequestsTests(unittest.TestCase):
    def test_posts_soql_with_app_token_and_returns_json_records(self):
        records = [{"service_request_id": "123", "requested_datetime": "2026-11-25T23:55:53.000"}]
        response = Response()
        response.status_code = 200
        response._content = json.dumps(records).encode("utf-8")
        with patch.dict(os.environ, {"SOCOTRA_SECRET": " test-app-token "}), \
                patch("requests.Session.send", return_value=response) as send:
            self.assertEqual(fetch_latest_requests(), records)

        request = send.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url, "https://data.sf.gov/api/v3/views/vw6y-z8j6/query.json")
        self.assertEqual(request.headers["X-App-Token"], "test-app-token")
        self.assertEqual(request.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(request.body)["query"], (
            "SELECT * WHERE requested_datetime IS NOT NULL "
            "ORDER BY requested_datetime DESC, service_request_id DESC LIMIT 100"
        ))
        self.assertEqual(send.call_args.kwargs["timeout"], 60)

    def test_reports_missing_or_rejected_app_token(self):
        with patch.dict(os.environ, {"SOCOTRA_SECRET": ""}):
            with self.assertRaisesRegex(RequestException, "SOCOTRA_SECRET"):
                fetch_latest_requests()

        response = Response()
        response.status_code = 403
        with patch.dict(os.environ, {"SOCOTRA_SECRET": "test-app-token"}), \
                patch("requests.Session.send", return_value=response):
            with self.assertRaisesRegex(HTTPError, "HTTP 403.*SOCOTRA_SECRET"):
                fetch_latest_requests()
