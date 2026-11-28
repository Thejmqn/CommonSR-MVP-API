"""Retrieve Seattle service requests from SODA 3.0 and convert them to CommonSR."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from requests.exceptions import RequestException

from common_sr import coordinate, load_label_mapping, pacific_timestamp
from soda3 import query_records


QUERY_URL = "https://data.seattle.gov/api/v3/views/5ngg-rpne/query.json"
SOQL = (
    "SELECT * WHERE createddate IS NOT NULL AND servicerequestnumber IS NOT NULL "
    "ORDER BY createddate DESC, servicerequestnumber DESC LIMIT 100"
)
AGENCY_MAPPINGS = "Specifications/seattle_agency_mappings.csv"
REQUEST_MAPPINGS = "Specifications/seattle_request_mappings.csv"
SEATTLE_METADATA = {
    "id": 2,
    "maintainer": "https://github.com/Thejmqn",
    "source": "https://data.seattle.gov/City-Administration/Customer-Service-Requests/5ngg-rpne/about_data",
    "agency_mappings": AGENCY_MAPPINGS,
    "request_mappings": REQUEST_MAPPINGS,
    "time_zone": "PST",
    "daylight_savings": True,
    "sub_1": "Council District",
    "sub_2": "Police Precinct",
    "sub_3": "Community Reporting Area",
    "notes": [
        "Seattle does not publish modification or closure timestamps in this dataset. Modified and closed are null for all records.",
        "Created timestamps without an offset are interpreted in Seattle local time (America/Los_Angeles).",
        "Reported and Transferred to Other Dept are in_progress. Closed is resolved. Canceled, incomplete, and closed duplicate cases are rejected.",
        "The source contains selected service request types and has no description field.",
        "Unmapped, missing, and ambiguous agency and request labels have a null clean value.",
    ],
}
STATUS_MAP = {
    "new": "open",
    "open": "open",
    "duplicate (open)": "open",
    "reported": "in_progress",
    "transferred to other dept": "in_progress",
    "closed": "resolved",
    "closed as duplicate": "rejected",
    "duplicate (closed)": "rejected",
    "closed -incomplete information": "rejected",
    "canceled": "rejected",
}


def fetch_latest_requests() -> list[dict]:
    """Return the latest 100 published Seattle service requests."""
    return query_records(QUERY_URL, SOQL, "Seattle")


def convert_seattle_results(records: list[dict]) -> dict:
    """Convert Seattle requests to the CommonSR response envelope."""
    agencies = load_label_mapping(AGENCY_MAPPINGS, "agency")
    requests = load_label_mapping(REQUEST_MAPPINGS, "request")
    results = []
    for record in records:
        raw_status = record.get("servicerequeststatusname")
        status = STATUS_MAP.get((raw_status or "").strip().casefold())
        if status is None:
            raise ValueError(f"Unsupported Seattle request status: {raw_status!r}")
        agency = record.get("departmentname")
        request = record.get("webintakeservicerequests")
        results.append({
            "id": str(record["servicerequestnumber"]),
            "status": status,
            "opened": pacific_timestamp(record["createddate"]),
            "modified": None,
            "closed": None,
            "address": record.get("location"),
            "latitude": coordinate(record.get("latitude")),
            "longitude": coordinate(record.get("longitude")),
            "sub_1": record.get("councildistrict") or None,
            "sub_2": record.get("policeprecinct") or None,
            "sub_3": record.get("community_reporting_area") or None,
            "agency": {"raw": agency, "clean": agencies.get(agency)},
            "request": {"raw": request, "clean": requests.get(request)},
            "description": None,
        })
    return {"cities": ["seattle"], "meta": {"seattle": deepcopy(SEATTLE_METADATA)}, "data": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Convert saved raw Seattle JSON instead of querying the API")
    parser.add_argument("--output", type=Path, default=Path("seattle_311_common_sr.json"), help="CommonSR JSON output path")
    args = parser.parse_args()
    try:
        records = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch_latest_requests()
        results = convert_seattle_results(records)
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except RequestException as exc:
        parser.exit(1, f"Unable to retrieve Seattle requests: {exc}\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Unable to convert Seattle requests: {exc}\n")
    print(f"Saved {len(results['data'])} CommonSR requests to {args.output}")


if __name__ == "__main__":
    main()
