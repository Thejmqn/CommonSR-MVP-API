"""Retrieve SF 311 cases from SODA 3.0 and convert them to CommonSR."""

import argparse
import json
import os
from pathlib import Path

import requests
from requests.exceptions import HTTPError, RequestException

from common_sr import convert_sf_results

QUERY_URL = "https://data.sf.gov/api/v3/views/vw6y-z8j6/query.json"
SOQL = (
    "SELECT * WHERE requested_datetime IS NOT NULL "
    "ORDER BY requested_datetime DESC, service_request_id DESC LIMIT 100"
)


def fetch_latest_requests() -> list[dict]:
    """Return raw cases, newest first, from the SODA 3.0 query endpoint."""
    token = os.environ.get("SOCOTRA_SECRET", "").strip()
    if not token:
        raise RequestException("Set SOCOTRA_SECRET to a valid Socrata application token.")

    response = requests.post(
        QUERY_URL,
        headers={"Accept": "application/json", "X-App-Token": token},
        json={"query": SOQL, "includeSystem": False, "includeSynthetic": False},
        timeout=60,
    )
    if response.status_code in (401, 403):
        raise HTTPError(
            f"SF SODA 3.0 denied the request (HTTP {response.status_code}). Check SOCOTRA_SECRET.",
            response=response,
        )
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise RequestException("SF SODA 3.0 returned an unexpected JSON response.")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        help="Convert an existing raw SF JSON array instead of querying the API",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("sf_311_common_sr.json"),
        help="CommonSR JSON output path (default: sf_311_common_sr.json)",
    )
    args = parser.parse_args()
    try:
        records = (
            json.loads(args.input.read_text(encoding="utf-8"))
            if args.input else fetch_latest_requests()
        )
        results = convert_sf_results(records)
    except RequestException as exc:
        parser.exit(1, f"Unable to retrieve SF 311 requests: {exc}\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Unable to convert SF 311 requests: {exc}\n")
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(results['data'])} CommonSR requests to {args.output}")


if __name__ == "__main__":
    main()
