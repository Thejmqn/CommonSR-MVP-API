"""Retrieve Baton Rouge 311 requests from SODA 3.0 and convert them to CommonSR."""

import argparse
import json
from copy import deepcopy
from pathlib import Path
from zoneinfo import ZoneInfo

from requests.exceptions import RequestException

from common_sr import coordinate, load_label_mapping, local_timestamp
from soda3 import query_records


QUERY_URL = "https://data.brla.gov/api/v3/views/7ixm-mnvx/query.json"
SOQL = (
    "SELECT * WHERE createdate IS NOT NULL AND id IS NOT NULL "
    "ORDER BY createdate DESC, id DESC LIMIT 100"
)
BATON_ROUGE_TIME_ZONE = ZoneInfo("America/Chicago")
AGENCY_MAPPINGS = "Specifications/baton_rouge_agency_mappings.csv"
REQUEST_MAPPINGS = "Specifications/baton_rouge_request_mappings.csv"
PARENT_TYPE_MAPPINGS = "Specifications/baton_rouge_parent_type_mappings.csv"
BATON_ROUGE_METADATA = {
    "id": 3,
    "maintainer": "https://github.com/Thejmqn",
    "source": "https://data.brla.gov/Government/311-Citizen-Requests-for-Service/7ixm-mnvx",
    "agency_mappings": AGENCY_MAPPINGS,
    "request_mappings": REQUEST_MAPPINGS,
    "time_zone": "CST",
    "daylight_savings": True,
    "sub_1": None,
    "sub_2": None,
    "sub_3": None,
    "notes": [
        "Baton Rouge provides no directly reported subdivision fields in this dataset. All three subdivision fields are null.",
        "Timestamps without an offset are interpreted in Baton Rouge local time (America/Chicago).",
        "Closed cases are represented as resolved. A missing Last Action Date or Close Date is null.",
        "A source coordinate pair of (0, 0) represents an unavailable location.",
        f"Request types without a direct mapping use the closest CommonSR type from {PARENT_TYPE_MAPPINGS}.",
        "Unmapped agencies and requests have a null clean value.",
    ],
}
STATUS_MAP = {"open": "open", "in progress": "in_progress", "closed": "resolved"}


def fetch_latest_requests() -> list[dict]:
    """Return the latest 100 published Baton Rouge service requests."""
    return query_records(QUERY_URL, SOQL, "Baton Rouge")


def convert_baton_rouge_results(records: list[dict]) -> dict:
    """Convert Baton Rouge requests to the CommonSR response envelope."""
    agencies = load_label_mapping(AGENCY_MAPPINGS, "agency")
    requests = load_label_mapping(REQUEST_MAPPINGS, "request")
    parents = load_label_mapping(PARENT_TYPE_MAPPINGS, "parent_type")
    results = []
    for record in records:
        raw_status = record.get("statusdesc")
        status = STATUS_MAP.get((raw_status or "").strip().casefold())
        if status is None:
            raise ValueError(f"Unsupported Baton Rouge request status: {raw_status!r}")

        agency = record.get("deptdiv")
        request = record.get("typename")
        clean_request = requests.get(request) or parents.get(record.get("parenttype"))
        address = [(record.get(field) or "").strip() for field in ("streetaddress", "cityname")]
        last_action = record.get("lastaction")
        close_date = record.get("closeddate")
        latitude = coordinate(record.get("latitude"))
        longitude = coordinate(record.get("longitude"))
        if latitude == longitude == 0:
            latitude = longitude = None

        results.append({
            "id": str(record["id"]),
            "status": status,
            "opened": local_timestamp(record["createdate"], BATON_ROUGE_TIME_ZONE),
            "modified": local_timestamp(last_action, BATON_ROUGE_TIME_ZONE) if last_action else None,
            "closed": local_timestamp(close_date, BATON_ROUGE_TIME_ZONE) if status == "resolved" and close_date else None,
            "address": ", ".join(part for part in address if part) or None,
            "latitude": latitude,
            "longitude": longitude,
            "sub_1": None,
            "sub_2": None,
            "sub_3": None,
            "agency": {"raw": agency, "clean": agencies.get(agency)},
            "request": {"raw": request, "clean": clean_request},
            "description": record.get("comments"),
        })
    return {"cities": ["baton_rouge"], "meta": {"baton_rouge": deepcopy(BATON_ROUGE_METADATA)}, "data": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Convert saved raw Baton Rouge JSON instead of querying the API")
    parser.add_argument("--output", type=Path, default=Path("baton_rouge_311_common_sr.json"), help="CommonSR JSON output path")
    args = parser.parse_args()
    try:
        records = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch_latest_requests()
        results = convert_baton_rouge_results(records)
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except RequestException as exc:
        parser.exit(1, f"Unable to retrieve Baton Rouge requests: {exc}\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Unable to convert Baton Rouge requests: {exc}\n")
    print(f"Saved {len(results['data'])} CommonSR requests to {args.output}")


if __name__ == "__main__":
    main()
