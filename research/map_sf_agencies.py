"""Fetch and classify exact SF Responsible Agency values for CommonSR."""

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.exceptions import HTTPError


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research" / "san_francisco_agency_evidence.json"
OUTPUT = ROOT / "Specifications" / "san_francisco_agency_mappings.csv"
DATASET_SOURCE = "https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/about_data"
RESOURCE_URL = "https://data.sf.gov/resource/vw6y-z8j6.json"
DIRECTORY_SOURCE = "https://www.sfgov.org/sfc/coordinators"
PW_SOURCE = "https://sfpublicworks.org/index.php/node/35306"
CBD_SOURCE = "https://www.sf.gov/sites/default/files/2023-05/Roadmap%20to%20Downtown%20San%20Francisco%27s%20Future%20-%20May%202023%20Update.pdf"
HSOC_SOURCE = "https://hsh.sfgov.org/wp-content/uploads/2018/10/FAQ-Strategic-Framework-10.16.18.pdf"
PUC_SOURCE = "https://www.sfpuc.gov/construction-contracts/new-developments"


def classification(clean, notes, confidence="high", review=False, source=DIRECTORY_SOURCE):
    return {
        "agency_clean": clean,
        "mapping_confidence": confidence,
        "review_required": str(review).lower(),
        "mapping_notes": notes,
        "evidence_urls": DATASET_SOURCE + "; " + source,
    }


def classify_agency(raw):
    # Normalization is only for classification; CSV keys preserve the exact raw text.
    name = re.sub(r"^\{DEPRECATED - DO NOT USE\}\s*", "", raw)
    name = " ".join(name.split())

    # Ambiguous workflow names receive explicit provisional assignments, never a
    # silent catch-all. Service-category evidence is supporting context, not proof
    # that a particular department owns the queue.
    if name in {"Noise Report", "Noise Report Queue"}:
        return classification("Customer Service", "Generic noise intake queue; no responding agency is identified. Provisional intake classification, not an assertion of Police or Health ownership.", "low", True, DATASET_SOURCE)
    if name == "Good Neighbor Policy":
        return classification("Sanitation", "Queue owner is unspecified. Aggregate records predominantly concern street cleaning and graffiti; provisional functional assignment requires owner confirmation.", "low", True, DATASET_SOURCE)
    if name == "Graffiti Abatement - Internal Queue":
        return classification("Sanitation", "Internal graffiti-removal workflow; provisional street-cleaning function. The responsible organization is not identified in the queue name.", "medium", True, DATASET_SOURCE)
    if name == "CCC - Community Branch":
        return classification("Health", "Historical CCC Community Branch queue; 133 of 147 records are General Request - DPH. Health is inferred; branch ownership needs confirmation.", "medium", True, DATASET_SOURCE)
    if name == "HSOC PHC Queue":
        return classification("Public Safety", "Multi-agency HSOC queue; 927 of 996 records are General Request - SFPD. Public Safety is a provisional dominant-routing assignment; PHC expansion is unverified.", "medium", True, HSOC_SOURCE)
    if name in {"Face Covering Report Queue", "Travel Quarantine Report Queue"}:
        return classification("Public Safety", "Historical pandemic reporting queue; published service categories predominantly identify SFPD. Classification follows enforcement routing rather than the health topic; confirm historical ownership.", "medium", True, DATASET_SOURCE)
    if name == "Triage - TTX Queue":
        return classification("Finance", "TTX denotes Treasurer and Tax Collector; tax-related requests support Finance. Queue also contains general 311 triage and requires review.", "medium", True, "https://sftreasurer.org/")
    if name == "SSP Restaurant Pre-Screening Application Queue":
        return classification("Health", "Only published record is General Request - DPH. Provisional Health assignment; SSP expansion and restaurant-screening queue owner are unverified.", "low", True, DATASET_SOURCE)
    if name == "SFGOV Work Request Queue":
        return classification("Customer Service", "Three records span unrelated service areas; SFGOV is insufficient to establish Technology ownership. Provisional general-routing classification.", "low", True, DATASET_SOURCE)
    if name in {"Demo", "Rapid Deploy Queue", "Interaction Generic", "Current Events", "Queue Management", "Case Review", "Knowledge Solutions", "CSP Escalation Review Queue", "SSP Inbound QA Queue"}:
        return classification("Customer Service", "Generic, historical, or demonstration workflow queue. Assigned to intake/knowledge/quality-assurance functions provisionally; responding organization is not established.", "low", True, DATASET_SOURCE)
    if name.startswith(("Healthy Streets Operation Center", "HSOC")) or name == "Tent Count":
        return classification("Human Services", "Homelessness and encampment coordination across multiple departments. Human Services represents the coordinating role; individual cases can involve sanitation, health, and police.", "medium", True, HSOC_SOURCE)

    if name.startswith(("311", "SF311")) or name in {"Duplicate Case Hold", "Duplicate Case Hold Queue", "Complaint Follow Up Queue", "Customer Satisfaction Work Queue", "Phone Outbound Queue"}:
        return classification("Customer Service", "311 intake, information, escalation, quality assurance, or case-holding workflow; not the downstream service department.", source=DATASET_SOURCE)
    if name.startswith("Animal Care and Control"):
        return classification("Animals", "Animal Care and Control agency; retain animal-related function even for emergency or dead-animal requests.")
    if name.startswith("Recology"):
        return classification("Sanitation", "External refuse and recycling operator; includes abandoned waste, litter, overflowing bins, and operator-noise complaints.", source="https://www.recology.com/recology-san-francisco/")
    if "CBD" in name:
        return classification("Sanitation", "Community Benefit District clean-and-safe crew handling 311 street/sidewalk cleaning and graffiti. Sanitation represents this operational role.", "medium", False, CBD_SOURCE)
    if name.startswith(("AT and T", "ATT")):
        return classification("Technology", "External telecommunications asset owner; graffiti refers to telecom equipment. Technology follows the connectivity provider's role, not the graffiti request type.", "medium", False, DATASET_SOURCE)

    if name.startswith(("DPW", "PW -")):
        if any(s in name for s in ("Street Environmental Services", "Street and Environmental Services", "Hotspot")):
            return classification("Sanitation", "Public Works street/environmental cleaning operation; street sweeping, litter, graffiti, and encampment cleanup.", source=PW_SOURCE)
        if any(s in name for s in ("Urban Forestry", "BUF")):
            return classification("Parks and Recreation", "Public Works urban-forestry division; tree and urban-green-space stewardship.", source="https://sfpublicworks.org/trees")
        if any(s in name for s in ("Street Use and Mapping", "BSM")):
            return classification("Permits and Code Enforcement", "Public Works Bureau of Street Use and Mapping; public-right-of-way permits, inspections, and enforcement.", source="https://sfpublicworks.org/services/permits/application-forms")
        if "Building Repair" in name:
            return classification("General Services", "Public Works municipal-building and facility repair function; includes civic structures and call-box assets.", source="https://sfpublicworks.org/")
        return classification("Public Works", "Public Works infrastructure repair, construction, or department-wide operations. Broad queues retain the parent department category rather than guessing a case-specific function.", source="https://sfpublicworks.org/")

    if name.startswith(("RPD", "RecPark", "Rec and Park")):
        return classification("Parks and Recreation", "Recreation and Park Department, including park patrol, maintenance, forestry, permits, and internal support for park services.", source="https://sfrecpark.org/")
    if name.startswith(("PUC", "PG and E", "PGE", "Fire Hydrant Maintenance")):
        return classification("Utilities", "Water, wastewater, power, or utility-owned streetlight/hydrant assets. Utility billing and support retain the utility agency category.", source=PUC_SOURCE + "; https://www.sfpuc.gov/construction-contracts/new-developments/street-pedestrian-lighting")
    if name.startswith(("MTA", "SFMTA", "DPT", "MUNI", "Muni", "SSP - MTA", "Taxi Commission", "TAXI", "Parking Enforcement", "Clear Channel - Transit", "Airport")):
        return classification("Transportation", "Transportation agency or transit/airport operator; includes parking, signals, signs, mobility, taxi regulation, transit shelters, and agency-specific support/permits.", source="https://www.sfmta.com/services")
    if name.startswith("Port Authority"):
        return classification("Transportation", "Port/waterfront authority. Transportation is the closest maritime-agency category, but the Port also manages property and public spaces; confirm this cross-functional choice.", "medium", True, "https://www.sfport.com/")

    if name.startswith("DBI"):
        return classification("Permits and Code Enforcement", "Department of Building Inspection: building, electrical, plumbing, housing-code inspections, permits, and plan review. Housing inspection is regulatory rather than housing assistance.", source="https://www.sf.gov/departments/department-building-inspection")
    if name.startswith(("Planning", "Entertainment Commission", "EC Venue Permit", "Shared Spaces", "Short Term Rentals", "Office of Cannabis", "Board of Appeals", "Film Commission", "Labor Standards Enforcement")):
        return classification("Permits and Code Enforcement", "Land-use, building/business/entertainment/film licensing, permit appeals, or regulatory enforcement function.", source="https://sfpublicworks.org/services/permits/application-forms; https://www.sf.gov/step-by-step--get-permit-film-san-francisco")
    if name.startswith("DPH") or name.startswith("Medical Examiner"):
        return classification("Health", "Department of Public Health or medical examiner; includes environmental-health regulation, clinical outreach, public-health records, and health hazards.", source="https://www.sf.gov/departments/department-public-health")
    if name.startswith(("Housing Authority", "Rent Board", "Redevelopment Agency", "Mayors Office - Housing", "Mayors Office on Housing", "Mayors Office of Community Development", "Mayors Office - Community Development")):
        return classification("Housing", "Public housing, rent regulation, housing assistance, or housing/community development.", source="https://www.sf.gov/departments/mayors-office-housing-and-community-development")
    if name.startswith(("HSA", "HSH", "Human Services Agency", "Aging and Adult Services", "Disability and Aging", "Children, Youth and Families", "Child Support Services", "Human Rights Commission", "Immigrant Rights Commission", "Status of Women", "Office on Disability", "Mayors Office - Disability", "Mayors Office on Disability", "Mayors Office - Victim Rights")):
        return classification("Human Services", "Resident support, social benefits, homelessness/shelter services, family assistance, accessibility, or civil-rights services. Benefit payments are not municipal Finance.", source="https://www.sfhsa.org/; https://hsh.sfgov.org/")
    if name.startswith(("Police", "Office of Citizens Complaints", "Sheriff", "SFFD", "Fire Department", "Emergency Management")):
        return classification("Public Safety", "Police, police oversight, sheriff, fire prevention/response, or emergency management.", source="https://www.sanfranciscopolice.org/; https://sf-fire.org/")
    if name.startswith(("Adult Probation", "Juvenile Probation", "District Attorney", "Public Defender", "Mayors Office of Criminal Justice")):
        return classification("Public Safety", "Criminal-justice function grouped with Public Safety. The current taxonomy has no distinct Justice/Legal Services type; review this consolidation.", "medium", True)
    if name.startswith("Controller"):
        return classification("Finance", "City financial oversight, accounting, and fiscal administration.", source="https://www.sf.gov/departments/controllers-office")
    if name.startswith("Risk Management"):
        return classification("Finance", "Insurance, claims, and municipal financial-risk administration; closest Finance fit, subject to review.", "medium", True)
    if name.startswith("Technology"):
        return classification("Technology", "Department of Technology, including public Wi-Fi and technical support.", source="https://www.sfgov.org/sfc/web-services")

    if name.startswith(("Environment",)):
        clean = "Utilities" if "EV Site Nomination" in name else "General Services"
        return classification(clean, "Taxonomy gap: no Environment/Sustainability type. Provisional closest category; EV siting uses Utilities, while general environmental administration uses General Services. Review before adopting.", "low", True)
    if name.startswith(("Art Commission", "Asian Art Museum", "Grants for the Arts", "War Memorial", "Library", "City College")):
        return classification("General Services", "Taxonomy gap: no Arts/Culture, Libraries, or Education type. Provisional General Services fit for municipal institutions/facilities; review before adopting.", "low", True)
    if name.startswith(("Small Business", "Office of Small Business", "Economic and Workforce Development")):
        return classification("General Services", "Taxonomy gap: no Business/Economic Development type. Provisional General Services classification for business support and economic administration; review before adopting.", "low", True)
    if name.startswith("Treasure Island Development Authority"):
        return classification("General Services", "Cross-functional development authority managing public land, infrastructure, and redevelopment. Provisional General Services fit; no Development Authority type exists.", "medium", True)
    if name.startswith(("Mayors Office of Neighborhood Services", "Mayors Office - Neighborhood Services", "Mayors Office Meeting Request", "Language Services")):
        return classification("Customer Service", "Constituent/neighborhood liaison, public meeting access, or language-access support.", "medium")
    if name.startswith(("Board of Supervisors", "BOS/Mayor", "Clerk of the Board", "City Administrator", "City Attorney", "City Hall", "Central Shops", "Contract", "Convention Facilities", "Elections", "Ethics Commission", "Human Resources", "Real Estate", "US Postal Service Maintenance")):
        return classification("General Services", "Municipal administration, governance, legal/procurement/HR support, civic facilities, fleet, or property maintenance. External postal assets use the same facilities role.", "medium")
    raise ValueError(f"Unclassified Responsible Agency: {raw!r}")


def write_mappings():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    with (ROOT / "research" / "common_sr_agency_types.csv").open(encoding="utf-8-sig", newline="") as source:
        allowed = {row["agency_clean"] for row in csv.DictReader(source)}
    rows = []
    errors = []
    for record in evidence["agencies"]:
        raw = record.get("agency_responsible")
        if raw is None:
            raise ValueError("Missing agency value requires a separate explicit policy")
        try:
            mapped = classify_agency(raw)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        assert mapped["agency_clean"] in allowed
        rows.append({
            "agency_raw": raw,
            **mapped,
            "request_count": int(record["request_count"]),
            "is_deprecated": str(bool(re.search(r"DEPRECATED|DO NOT USE", raw, re.I))).lower(),
            "source_retrieved_at_utc": evidence["retrieved_at_utc"],
        })
    if errors:
        raise ValueError("\n".join(errors))
    assert len(rows) == len({r["agency_raw"] for r in rows}) == int(evidence["totals"]["distinct_named_agencies"])
    assert sum(r["request_count"] for r in rows) == int(evidence["totals"]["request_count"])
    fields = ["agency_raw", "agency_clean", "request_count", "mapping_confidence", "review_required", "is_deprecated", "mapping_notes", "evidence_urls", "source_retrieved_at_utc"]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["agency_raw"]))
    with OUTPUT.open(encoding="utf-8-sig", newline="") as target:
        saved = list(csv.DictReader(target))
    assert {r["agency_raw"] for r in saved} == {r["agency_responsible"] for r in evidence["agencies"]}
    assert all(r["agency_clean"] in allowed and r["mapping_notes"] for r in saved)
    by_raw = {r["agency_raw"]: r for r in saved}
    expected = {
        "DPW Ops Queue": "Public Works",
        "PW - Street and Environmental Services": "Sanitation",
        "DPW BSM Queue": "Permits and Code Enforcement",
        "DPW BUF Queue": "Parks and Recreation",
        "PW - Building Repair": "General Services",
        "PUC Streetlights Queue": "Utilities",
        "PUC - Billing": "Utilities",
        "DPH Environmental Health - Solid Waste": "Health",
        "DBI Housing Inspection Queue": "Permits and Code Enforcement",
        "Housing Authority SR Queue": "Housing",
        "MTA - Citations/RPP Accounting": "Transportation",
        "Recology - Noise": "Sanitation",
        "Animal Care and Control - Animal Emergency": "Animals",
    }
    for raw, clean in expected.items():
        assert by_raw[raw]["agency_clean"] == clean, raw
    for row in saved:
        if row["mapping_confidence"] == "low":
            assert row["review_required"] == "true"
    deprecated_pairs = [(r["agency_raw"], r["agency_raw"].removeprefix("{DEPRECATED - DO NOT USE} ")) for r in saved if r["agency_raw"].startswith("{DEPRECATED - DO NOT USE}")]
    for deprecated, active in deprecated_pairs:
        if active in by_raw:
            assert by_raw[deprecated]["agency_clean"] == by_raw[active]["agency_clean"]
    print(f"Saved {len(rows)} mappings to {OUTPUT}")
    print("Mappings by type:", dict(Counter(r["agency_clean"] for r in rows)))
    print("Rows flagged for review:", sum(r["review_required"] == "true" for r in rows))


def query_agencies(soql, token=None):
    """Read the research data from the same public resource endpoint."""
    response = requests.get(
        RESOURCE_URL,
        params={"$query": soql},
        headers={"X-App-Token": token} if token else None,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def fetch_agencies():
    tokens = list(dict.fromkeys([os.environ.get("SOCOTRA_SECRET") or None, None]))
    for token in tokens:
        try:
            rows = query_agencies(
                "SELECT agency_responsible, count(*) AS request_count "
                "GROUP BY agency_responsible ORDER BY agency_responsible ASC LIMIT 50000",
                token,
            )
            totals = query_agencies(
                "SELECT count(*) AS request_count, "
                "count(distinct agency_responsible) AS distinct_named_agencies",
                token,
            )[0]
            break
        except HTTPError as exc:
            if token and exc.response.status_code == 403 and "Invalid app_token" in exc.response.text:
                print("Configured application token was rejected; retrying public access.")
                continue
            raise
    evidence = {
        "source": "https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/about_data",
        "endpoint": RESOURCE_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "All published records, including historical and deprecated queues",
        "totals": totals,
        "agencies": rows,
    }
    named = [r for r in rows if r.get("agency_responsible") is not None]
    assert len(named) == int(totals["distinct_named_agencies"]), "Incomplete agency inventory"
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Retrieved {len(rows)} exact agency values; {len(named)} named agencies")
    print(f"Total published requests: {totals['request_count']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--map", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        fetch_agencies()
    if args.inspect:
        inspect_queues()
    if args.map:
        write_mappings()


def inspect_queues():
    names = [
        "CCC - Community Branch", "Good Neighbor Policy", "Noise Report", "Noise Report Queue",
        "Triage - TTX Queue", "Demo", "SFGOV Work Request Queue", "Knowledge Solutions",
        "Rapid Deploy Queue", "Face Covering Report Queue", "Travel Quarantine Report Queue",
        "HSOC PHC Queue", "Tent Count", "SSP Restaurant Pre-Screening Application Queue",
        "CSP Escalation Review Queue", "Environment", "Environment - G",
    ]
    values = ", ".join("'" + name.replace("'", "''") + "'" for name in names)
    rows = query_agencies(
        "SELECT agency_responsible, service_name, count(*) AS request_count "
        f"WHERE agency_responsible IN ({values}) "
        "GROUP BY agency_responsible, service_name "
        "ORDER BY agency_responsible ASC, request_count DESC LIMIT 5000"
    )
    target = ROOT / "research" / "san_francisco_ambiguous_queue_evidence.json"
    target.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    for name in names:
        print(name + ": " + json.dumps([r for r in rows if r["agency_responsible"] == name][:4]))


if __name__ == "__main__":
    main()
