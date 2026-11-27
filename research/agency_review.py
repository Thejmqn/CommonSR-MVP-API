"""Read-only agency inventory for the 20-city CommonSR source directory."""

import concurrent.futures
import csv
import json
import re
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research" / "agency_review_evidence.json"


def read_city(row):
    city, url = row["City"], row["Dataset URL"]
    item = {"city": city, "source": url}
    match = re.search(r"https://([^/]+)/(?:.*/)?([a-z0-9]{4}-[a-z0-9]{4})(?:/|$)", url)
    if not match:
        item["status"] = "Non-Socrata source; inspect separately"
        return item
    domain, dataset = match.groups()
    try:
        response = requests.get(f"https://{domain}/api/views/{dataset}.json", timeout=35)
        response.raise_for_status()
        meta = response.json()
        item["title"] = meta.get("name")
        columns = [c["fieldName"] for c in meta.get("columns", []) if not c["fieldName"].startswith(":")]
        item["columns"] = columns
        fields = [f for f in columns if re.search(r"agency|department|dept|bureau|division|responsible|assigned|owner", f)]
        item["agency_fields"] = fields
        item["values"] = {}
        endpoint = f"https://{domain}/resource/{dataset}.json"
        item["endpoint"] = endpoint
        for field in fields:
            query = f"SELECT {field}, count(*) AS records GROUP BY {field} ORDER BY records DESC LIMIT 1000"
            result = requests.get(endpoint, params={"$query": query}, timeout=50)
            if result.ok:
                item["values"][field] = result.json()
            else:
                item["values"][field] = {"error": result.status_code, "message": result.text[:200]}
        if not fields:
            response = requests.get(endpoint, params={"$limit": 3}, timeout=25)
            item["sample"] = response.json()
        item["status"] = "Reviewed" if fields else "No explicit agency field"
    except Exception as exc:
        item["status"] = "Error"
        item["error"] = str(exc)
    return item


def main():
    if "--follow-up" in sys.argv:
        follow_up()
        return
    with (ROOT / "Specifications" / "us_311_open_data_directory.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for item in executor.map(read_city, rows):
            results.append(item)
            print(json.dumps({k: v for k, v in item.items() if k not in {"values", "sample"}}), flush=True)
    OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def follow_up():
    sources = [
        ("New York City", "data.cityofnewyork.us", "erm2-nwe9", ["agency", "agency_name"]),
        ("Chicago", "data.cityofchicago.org", "v6vf-nfxy", ["owner_department"]),
        ("Austin", "data.austintexas.gov", "38mr-dwji", ["department"]),
        ("Oakland", "data.oaklandca.gov", "quth-gb8e", ["referredto", "reqcategory"]),
    ]
    def inspect(source):
        city, domain, dataset, fields = source
        item = {"city": city, "endpoint": f"https://{domain}/resource/{dataset}.json", "cached_values": {}}
        response = requests.get(f"https://{domain}/api/views/{dataset}.json", timeout=30)
        response.raise_for_status()
        for column in response.json()["columns"]:
            if column["fieldName"] in fields:
                item["cached_values"][column["fieldName"]] = column.get("cachedContents", {})
        selected = fields if city != "Austin" else [c["fieldName"] for c in response.json()["columns"] if "department" in c["fieldName"].lower()]
        item["fields"] = selected
        try:
            sample = requests.get(item["endpoint"], params={"$select": ",".join(selected), "$limit": 10000}, timeout=35)
            sample.raise_for_status()
            rows = sample.json()
            item["sample_rows"] = len(rows)
            item["sample_values"] = {f: sorted({r[f] for r in rows if r.get(f)}) for f in selected}
        except Exception as exc:
            item["sample_error"] = str(exc)
        return item
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(inspect, source): source[0] for source in sources}
        for future in concurrent.futures.as_completed(futures):
            try:
                item = future.result()
            except Exception as exc:
                item = {"city": futures[future], "error": str(exc)}
            results.append(item)
            Path(__file__).with_name("agency_review_followup_evidence.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(item), flush=True)


if __name__ == "__main__":
    main()
