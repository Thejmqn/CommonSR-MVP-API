"""Convert raw SF 311 records to Specifications/query_results.md."""

import csv
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


SF_TIME_ZONE = ZoneInfo("America/Los_Angeles")
SF_AGENCY_MAPPINGS_PATH = Path(__file__).resolve().parent / "Specifications" / "san_francisco_agency_mappings.csv"
SF_REQUEST_EVIDENCE_PATH = Path(__file__).resolve().parent / "research" / "common_sr_request_type_evidence.json"
# Each alias points to the source pair whose CommonSR type it shares.
SF_REQUEST_ALIASES = {
    ("Graffiti Private", "not_offensive"): ("Graffiti Public", "not_offensive"),
    ("RPD General", "structural_maintenance"): ("Rec and Park Requests", "Park - Structural_Maintenance"),
    ("Noise", "entertainment"): ("Noise Report", "entertainment"),
    ("Parking Enforcement", "large_vehicle"): ("Parking Enforcement", "other_illegal_parking"),
}
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
        "Agency classifications use the SF mappings CSV, including provisional assignments pending review.",
        "Unmapped or missing agencies have a null clean value.",
        "Request classifications use the SF entries in the CommonSR request-type evidence.",
        "Unmapped or missing request types have a null clean value.",
    ],
}
STATUS_MAP = {
    "open": "open",
    "closed": "resolved",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "rejected": "rejected",
}


def load_sf_agency_mappings() -> dict[str, str]:
    """Read exact raw-to-clean assignments, including rows awaiting review."""
    mappings = {}
    with SF_AGENCY_MAPPINGS_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"agency_raw", "agency_clean"}.issubset(reader.fieldnames or []):
            raise ValueError("SF agency mappings require agency_raw and agency_clean columns")
        for row in reader:
            raw, clean = row["agency_raw"], row["agency_clean"]
            if not raw or not clean:
                raise ValueError("SF agency mappings must have nonempty raw and clean values")
            if raw in mappings:
                raise ValueError(f"Duplicate SF agency mapping: {raw!r}")
            mappings[raw] = clean
    return mappings


def _request_key(service_name: str, service_subtype: str) -> tuple[str, str]:
    return service_name.strip().casefold(), service_subtype.strip().casefold()


def load_sf_request_mappings() -> dict[tuple[str, str], str]:
    """Load standardized types from SF service name and subtype pairs."""
    with SF_REQUEST_EVIDENCE_PATH.open(encoding="utf-8") as source:
        evidence = json.load(source)
    mappings = {}
    for request_type in evidence["types"]:
        sf = request_type["city_evidence"].get("San Francisco")
        if sf is None:
            continue
        clean = request_type["request_type"]
        for group in sf["largest_raw_groups"]:
            key = _request_key(*group["labels"])
            if key in mappings and mappings[key] != clean:
                raise ValueError(f"Conflicting SF request mapping: {group['labels']!r}")
            mappings[key] = clean
    for alias, source_pair in SF_REQUEST_ALIASES.items():
        source_key = _request_key(*source_pair)
        if source_key in mappings:
            mappings.setdefault(_request_key(*alias), mappings[source_key])
    return mappings


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


def convert_sf_request(
    record: dict,
    agency_mappings: Mapping[str, str] | None = None,
    request_mappings: Mapping[tuple[str, str], str] | None = None,
) -> dict:
    """Convert one case without modifying its raw source record."""
    raw_status = record["status_description"].strip().lower().replace(" ", "_")
    if raw_status not in STATUS_MAP:
        raise ValueError(f"Unsupported SF case status: {raw_status!r}")
    status = STATUS_MAP[raw_status]
    district = record.get("supervisor_district")
    if agency_mappings is None:
        agency_mappings = load_sf_agency_mappings()
    if request_mappings is None:
        request_mappings = load_sf_request_mappings()
    raw_agency = record.get("agency_responsible")
    service_name = record.get("service_name") or ""
    service_subtype = record.get("service_subtype") or ""
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
        "agency": {"raw": raw_agency, "clean": agency_mappings.get(raw_agency)},
        "request": {
            "raw": " - ".join(label for label in (service_name, service_subtype) if label) or None,
            "clean": request_mappings.get(_request_key(service_name, service_subtype)),
        },
        "description": record.get("service_details") or None,
    }


def convert_sf_results(records: list[dict]) -> dict:
    """Wrap SF cases and metadata in the CommonSR response envelope."""
    agency_mappings = load_sf_agency_mappings()
    request_mappings = load_sf_request_mappings()
    return {
        "cities": ["san_francisco"],
        "meta": {"san_francisco": deepcopy(SF_METADATA)},
        "data": [convert_sf_request(record, agency_mappings, request_mappings) for record in records],
    }
