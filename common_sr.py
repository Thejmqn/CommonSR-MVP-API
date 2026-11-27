"""Convert raw SF 311 records to Specifications/query_results.md."""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo


SF_TIME_ZONE = ZoneInfo("America/Los_Angeles")
SF_METADATA = {
    "id": 1,
    "maintainer": "https://github.com/Thejmqn",
    "source": "https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/about_data",
    "agency_mappings": "https://www.servicerequest.org/agency-mappings/1",
    "request_mappings": "https://www.servicerequest.org/request-mappings/1",
    "time_zone": "PST",
    "daylight_savings": True,
    "sub_1": "Supervisor District",
    "sub_2": "Neighborhood",
    "sub_3": "Police District",
    "notes": [
        "SF Closed cases are represented as resolved.",
        "Agency and request fields are omitted pending mappings.",
    ],
}
STATUS_MAP = {
    "open": "open",
    "closed": "resolved",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "rejected": "rejected",
}


def _timestamp(value: str) -> dict[str, str]:
    if not value:
        raise ValueError("Required SF case timestamp is missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SF_TIME_ZONE)
    local = parsed.astimezone(SF_TIME_ZONE)
    return {
        "local": local.isoformat(),
        "utc": local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _coordinate(value) -> float | None:
    if value is None or value == "":
        return None
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("SF coordinates must be finite")
    return float(round(number, 8))


def convert_sf_request(record: dict) -> dict:
    """Convert one case without modifying its raw source record."""
    raw_status = record["status_description"].strip().lower().replace(" ", "_")
    if raw_status not in STATUS_MAP:
        raise ValueError(f"Unsupported SF case status: {raw_status!r}")
    status = STATUS_MAP[raw_status]
    district = record.get("supervisor_district")
    return {
        "id": str(record["service_request_id"]),
        "status": status,
        "opened": _timestamp(record.get("requested_datetime")),
        "modified": _timestamp(record.get("updated_datetime")),
        "closed": (
            None if status in {"open", "in_progress"}
            else _timestamp(record.get("closed_date"))
        ),
        "address": record.get("address"),
        "latitude": _coordinate(record.get("lat")),
        "longitude": _coordinate(record.get("long")),
        "sub_1": (
            format(Decimal(str(district)).normalize(), "f")
            if district is not None and district != "" else None
        ),
        "sub_2": record.get("neighborhoods_sffind_boundaries") or None,
        "sub_3": record.get("police_district") or None,
        "description": record.get("service_details") or None,
    }


def convert_sf_results(records: list[dict]) -> dict:
    """Wrap SF cases and metadata in the CommonSR response envelope."""
    return {
        "cities": ["san_francisco"],
        "meta": {"san_francisco": deepcopy(SF_METADATA)},
        "data": [convert_sf_request(record) for record in records],
    }
