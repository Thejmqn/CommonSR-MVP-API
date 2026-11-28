import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from requests import Response
from requests.exceptions import Timeout

from main import seattle_requests
from seattle311 import convert_seattle_results


def raw_case(**fields):
    return {
        "servicerequestnumber": "26-00355192",
        "createddate": "2026-07-20T01:11:45.000",
        "servicerequeststatusname": "Closed",
        "departmentname": "SDOT-Seattle Department of Transportation",
        "webintakeservicerequests": "Scooter or Bike Share Issue",
        "location": "Example location",
        "latitude": "47.606210124",
        "longitude": -122.332070129,
        "councildistrict": "7",
        "policeprecinct": "West",
        "community_reporting_area": "Downtown",
        **fields,
    }


class SeattleAdapterTests(unittest.TestCase):
    def test_route_queries_seattle_and_converts_records(self):
        response = Response()
        response.status_code = 200
        response._content = json.dumps([raw_case()]).encode("utf-8")
        with (
            patch.dict(os.environ, {"SOCOTRA_SECRET": "test-app-token"}),
            patch("requests.Session.send", return_value=response) as send,
        ):
            result = seattle_requests()

        request = send.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url, "https://data.seattle.gov/api/v3/views/5ngg-rpne/query.json")
        self.assertIn(
            "ORDER BY createddate DESC, servicerequestnumber DESC LIMIT 100",
            json.loads(request.body)["query"],
        )
        self.assertEqual(result["cities"], ["seattle"])
        self.assertEqual(result["meta"]["seattle"]["sub_3"], "Community Reporting Area")
        self.assertEqual(result["data"][0], {
            "id": "26-00355192",
            "status": "resolved",
            "opened": {"local": "2026-07-20T01:11:45-07:00", "utc": "2026-07-20T08:11:45Z"},
            "modified": None,
            "closed": None,
            "address": "Example location",
            "latitude": 47.60621012,
            "longitude": -122.33207013,
            "sub_1": "7",
            "sub_2": "West",
            "sub_3": "Downtown",
            "agency": {"raw": "SDOT-Seattle Department of Transportation", "clean": "Transportation"},
            "request": {"raw": "Scooter or Bike Share Issue", "clean": "Scooter or Bike Share Complaint"},
            "description": None,
        })

    def test_routed_and_duplicate_statuses_with_unmapped_labels(self):
        for raw_status, expected in [
            ("Reported", "in_progress"),
            ("Transferred to Other Dept", "in_progress"),
            ("Closed as Duplicate", "rejected"),
            ("Closed -Incomplete Information", "rejected"),
            ("Duplicate (Open)", "open"),
        ]:
            with self.subTest(status=raw_status):
                case = convert_seattle_results([raw_case(
                    servicerequeststatusname=raw_status,
                    departmentname="SEA-City of Seattle",
                    webintakeservicerequests="Street Sign and Traffic Signal Maintenance",
                    location=None,
                    latitude=None,
                )])["data"][0]
                self.assertEqual(case["status"], expected)
                self.assertIsNone(case["address"])
                self.assertIsNone(case["latitude"])
                self.assertEqual(case["agency"], {"raw": "SEA-City of Seattle", "clean": None})
                self.assertEqual(case["request"], {
                    "raw": "Street Sign and Traffic Signal Maintenance", "clean": None,
                })

    def test_route_reports_upstream_failure(self):
        with patch("main.fetch_seattle_requests", side_effect=Timeout("request timed out")):
            with self.assertRaises(HTTPException) as error:
                seattle_requests()
        self.assertEqual(error.exception.status_code, 502)
