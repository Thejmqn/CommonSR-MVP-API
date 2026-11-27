import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from requests.exceptions import Timeout

from common_sr import convert_sf_request, convert_sf_results
from main import san_francisco_requests


def raw_case(**overrides):
    case = {
        "service_request_id": "202000356863",
        "status_description": "Open",
        "requested_datetime": "2026-11-25T23:55:53.000",
        "updated_datetime": "2026-11-25T23:55:58.000",
        "address": "208 STRATFORD DR, SAN FRANCISCO, CA 94132, US",
        "lat": "37.7210491349",
        "long": "-122.4737738951",
        "supervisor_district": "7.0",
        "neighborhoods_sffind_boundaries": "Stonestown",
        "police_district": "TARAVAL",
        "status_notes": "  Original description.\nDo not edit.  ",
        "agency_responsible": "Deferred agency",
        "service_name": "Deferred request",
    }
    case.update(overrides)
    return case


class CommonSRTests(unittest.TestCase):
    def test_envelope_and_fields(self):
        source = [raw_case()]
        original = deepcopy(source)
        result = convert_sf_results(source)
        self.assertEqual(set(result), {"cities", "meta", "data"})
        self.assertEqual(result["cities"], ["san_francisco"])
        self.assertEqual(result["meta"]["san_francisco"]["id"], 1)
        self.assertIsInstance(result["meta"]["san_francisco"]["notes"], list)
        case = result["data"][0]
        self.assertEqual(set(case), {
            "id", "status", "opened", "modified", "closed", "address",
            "latitude", "longitude", "sub_1", "sub_2", "sub_3", "description",
        })
        self.assertEqual(case["id"], source[0]["service_request_id"])
        self.assertEqual(case["description"], source[0]["status_notes"])
        self.assertEqual(case["sub_1"], "7")
        self.assertEqual(case["sub_2"], "Stonestown")
        self.assertEqual(case["sub_3"], "TARAVAL")
        self.assertEqual(case["latitude"], 37.72104913)
        self.assertEqual(case["longitude"], -122.4737739)
        self.assertEqual(source, original)

    def test_winter_and_summer_timestamps(self):
        for date, offset, utc in [
            ("2026-11-25T23:55:53.000", "-08:00", "2026-11-26T07:55:53Z"),
            ("2026-07-25T23:55:53.000", "-07:00", "2026-07-26T06:55:53Z"),
        ]:
            with self.subTest(date=date):
                opened = convert_sf_request(raw_case(requested_datetime=date))["opened"]
                self.assertTrue(opened["local"].endswith(offset))
                self.assertEqual(opened["utc"], utc)
                self.assertEqual(
                    datetime.fromisoformat(opened["local"]).astimezone(timezone.utc),
                    datetime.fromisoformat(opened["utc"]),
                )

    def test_timezone_aware_input(self):
        case = convert_sf_request(raw_case(requested_datetime="2026-07-26T06:55:53Z"))
        self.assertEqual(case["opened"]["local"], "2026-07-25T23:55:53-07:00")

    def test_terminal_and_active_statuses(self):
        for source_status, expected in [
            ("Open", "open"), ("Closed", "resolved"),
            ("In Progress", "in_progress"), ("Rejected", "rejected"),
        ]:
            with self.subTest(status=source_status):
                case = convert_sf_request(raw_case(
                    status_description=source_status, closed_date="2026-11-26T01:00:00",
                ))
                self.assertEqual(case["status"], expected)
                if expected in {"open", "in_progress"}:
                    self.assertIsNone(case["closed"])
                else:
                    self.assertEqual(case["closed"]["utc"], "2026-11-26T09:00:00Z")

    def test_absent_optional_values_and_empty_description(self):
        case = convert_sf_request(raw_case(
            lat=None, long="", supervisor_district=None,
            neighborhoods_sffind_boundaries="", police_district=None, status_notes="",
        ))
        for field in ("latitude", "longitude", "sub_1", "sub_2", "sub_3"):
            self.assertIsNone(case[field])
        self.assertEqual(case["description"], "")
        source = raw_case()
        del source["status_notes"]
        self.assertIsNone(convert_sf_request(source)["description"])

    def test_invalid_required_data_is_not_invented(self):
        for overrides in [
            {"status_description": "Unknown"},
            {"requested_datetime": None},
            {"updated_datetime": None},
            {"status_description": "Closed"},
        ]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                convert_sf_request(raw_case(**overrides))

    def test_empty_results_and_metadata_independence(self):
        result = convert_sf_results([])
        self.assertEqual(result["data"], [])
        result["meta"]["san_francisco"]["notes"].append("changed")
        self.assertNotIn("changed", convert_sf_results([])["meta"]["san_francisco"]["notes"])

    def test_endpoint_returns_common_sr(self):
        with patch("main.fetch_latest_requests", return_value=[raw_case()]):
            self.assertEqual(san_francisco_requests(), convert_sf_results([raw_case()]))

    def test_endpoint_reports_upstream_and_conversion_errors(self):
        for kwargs in [
            {"side_effect": Timeout("API timeout")},
            {"return_value": [raw_case(status_description="Unknown")]},
        ]:
            with self.subTest(kwargs=kwargs), patch("main.fetch_latest_requests", **kwargs):
                with self.assertRaises(HTTPException) as raised:
                    san_francisco_requests()
                self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
