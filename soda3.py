"""Read records from Socrata's SODA 3.0 query API."""

import os

import requests
from requests.exceptions import HTTPError, RequestException


def query_records(url: str, soql: str, source: str) -> list[dict]:
    token = os.environ.get("SOCOTRA_SECRET", "").strip()
    if not token:
        raise RequestException("Set SOCOTRA_SECRET to a valid Socrata application token.")

    response = requests.post(
        url,
        headers={"Accept": "application/json", "X-App-Token": token},
        json={"query": soql, "includeSystem": False, "includeSynthetic": False},
        timeout=60,
    )
    if response.status_code in (401, 403):
        raise HTTPError(
            f"{source} SODA 3.0 denied the request (HTTP {response.status_code}). Check SOCOTRA_SECRET.",
            response=response,
        )
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise RequestException(f"{source} SODA 3.0 returned an unexpected JSON response.")
    return records
