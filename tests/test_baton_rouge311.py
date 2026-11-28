import json
import os
import unittest
from unittest.mock import patch

from requests import Response

from baton_rouge311 import convert_baton_rouge_results
from main import baton_rouge_requests


def raw_case(**fields):
    return {
        "id": "012345",
        "status": "3",
        "statusdesc": "CLOSED",
        "createdate": "2026-10-26T10:20:00.000",
        "lastaction": "2026-10-27T08:30:00.000",
        "closeddate": "2026-10-27T08:00:00.000",
        "streetaddress": "123 Example Street",
        "cityname": "Baton Rouge",
        "latitude": "30.451467823",
        "longitude": "-91.187149751",
        "deptdiv": "DOM - STREET MAINTENANCE",
        "typename": "POTHOLE",
        "parenttype": "ROAD MAINTENANCE ISSUES",
        "comments": "  Deep pothole beside the curb.\n",
        **fields,
    }


class BatonRougeAdapterTests(unittest.TestCase):
    def test_route_queries_baton_rouge_and_converts_records(self):
        response = Response()
        response.status_code = 200
        response._content = json.dumps([raw_case()]).encode("utf-8")
        with (
            patch.dict(os.environ, {"SOCOTRA_SECRET": "test-app-token"}),
            patch("requests.Session.send", return_value=response) as send,
        ):
            result = baton_rouge_requests()

        request = send.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url, "https://data.brla.gov/api/v3/views/7ixm-mnvx/query.json")
        self.assertIn("ORDER BY createdate DESC, id DESC LIMIT 100", json.loads(request.body)["query"])
        self.assertEqual(result["cities"], ["baton_rouge"])
        self.assertIsNone(result["meta"]["baton_rouge"]["sub_1"])
        self.assertEqual(result["data"][0], {
            "id": "012345",
            "status": "resolved",
            "opened": {"local": "2026-10-26T10:20:00-05:00", "utc": "2026-10-26T15:20:00Z"},
            "modified": {"local": "2026-10-27T08:30:00-05:00", "utc": "2026-10-27T13:30:00Z"},
            "closed": {"local": "2026-10-27T08:00:00-05:00", "utc": "2026-10-27T13:00:00Z"},
            "address": "123 Example Street, Baton Rouge",
            "latitude": 30.45146782,
            "longitude": -91.18714975,
            "sub_1": None,
            "sub_2": None,
            "sub_3": None,
            "agency": {"raw": "DOM - STREET MAINTENANCE", "clean": "Public Works"},
            "request": {"raw": "POTHOLE", "clean": "Pothole Repair"},
            "description": "  Deep pothole beside the curb.\n",
        })

    def test_parent_mapping_is_used_for_blank_and_unseen_types(self):
        for parenttype, typename, clean in [
            ("RECYCLING", "DAMAGE TO PERSONAL PROPERTY", "Garbage and Recycling Collection"),
            ("SEWER/WASTEWATER", "UNSEEN TYPE", "Sewer Inspection or Repair"),
            ("SEWER/WASTEWATER", None, "Sewer Inspection or Repair"),
            ("UNSEEN PARENT", "UNSEEN TYPE", None),
        ]:
            with self.subTest(parenttype=parenttype, typename=typename):
                result = convert_baton_rouge_results([raw_case(parenttype=parenttype, typename=typename)])
                self.assertEqual(result["data"][0]["request"], {"raw": typename, "clean": clean})

    def test_incomplete_and_active_records_preserve_missing_values(self):
        rows = [
            raw_case(statusdesc="IN PROGRESS", lastaction=None, streetaddress=None, latitude="0", longitude="0"),
            raw_case(statusdesc="CLOSED", closeddate=None, streetaddress=None, cityname=None),
        ]
        active, closed = convert_baton_rouge_results(rows)["data"]
        self.assertEqual(active["status"], "in_progress")
        self.assertEqual(active["address"], "Baton Rouge")
        for field in ("modified", "closed", "latitude", "longitude"):
            self.assertIsNone(active[field])
        self.assertEqual(closed["status"], "resolved")
        self.assertIsNone(closed["closed"])
        self.assertIsNone(closed["address"])
