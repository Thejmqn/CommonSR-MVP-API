"""Inspect agency fields in the directory's file, CKAN, CARTO and GIS sources."""

import concurrent.futures
import csv
import json
import re
import sys
import gzip
from pathlib import Path

import requests


OUT = Path(__file__).with_name("agency_review_other_evidence.json")
GIS = {
    "Denver": "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_service_requests_311/FeatureServer/0",
    "Washington, DC": "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/ServiceRequests/FeatureServer/18",
    "Charlotte": "https://gis.charlottenc.gov/arcgis/rest/services/ODP/ServiceRequests311/MapServer/0",
    "Baltimore": "https://services1.arcgis.com/UWYHeuuJISiGmgXx/ArcGIS/rest/services/311_Customer_Service_Requests_current/FeatureServer/0",
    "Nashville": "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/hubNashville_311_Service_Requests_Current_Year_view/FeatureServer/0",
}


def get(url, params=None):
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    return response.json()


def gis(city, url):
    item = {"city": city, "endpoint": url}
    meta = get(url, {"f": "json"})
    item["title"] = meta.get("name")
    item["columns"] = [f["name"] for f in meta.get("fields", [])]
    fields = [f for f in item["columns"] if re.search("agency|department|dept|bureau|division|responsible|assigned|owner", f, re.I)]
    item["agency_fields"] = fields
    item["values"] = {}
    for field in fields:
        item["values"][field] = get(url + "/query", {
            "f": "json", "where": "1=1", "outFields": field,
            "returnDistinctValues": "true", "returnGeometry": "false",
        })
    if not fields:
        item["sample"] = get(url + "/query", {
            "f": "json", "where": "1=1", "outFields": "*",
            "resultRecordCount": 2, "returnGeometry": "false",
        })
    return item


def ckan(city, base, resource):
    item = {"city": city, "endpoint": base}
    data = get(base + "/api/3/action/datastore_search", {"resource_id": resource, "limit": 1})
    item["columns"] = [f["id"] for f in data["result"]["fields"]]
    fields = [f for f in item["columns"] if re.search("agency|department|dept|bureau|division|responsible|assigned|owner", f, re.I)]
    item["agency_fields"] = fields
    item["values"] = {}
    for field in fields:
        sql = f'SELECT "{field}", count(*) AS records FROM "{resource}" GROUP BY "{field}" ORDER BY records DESC'
        item["values"][field] = get(base + "/api/3/action/datastore_search_sql", {"sql": sql})
    return item


def files(city, url, delimiter):
    item = {"city": city, "endpoint": url, "values": {}}
    with requests.get(url, timeout=30, stream=True) as response:
        response.raise_for_status()
        response.encoding = "utf-8-sig"
        reader = csv.DictReader(response.iter_lines(decode_unicode=True), delimiter=delimiter)
        item["columns"] = reader.fieldnames
        fields = [f for f in reader.fieldnames if re.search("agency|department|dept|bureau|division|responsible|assigned|owner|case_record_type", f, re.I)]
        item["agency_fields"] = fields
        values = {f: set() for f in fields}
        count = 0
        for row in reader:
            for field in fields:
                if row.get(field):
                    values[field].add(row[field])
            count += 1
            if count >= 100000:
                break
        item["rows_reviewed"] = count
        item["values"] = {f: sorted(v) for f, v in values.items()}
    return item


def philly():
    endpoint = "https://phl.carto.com/api/v2/sql"
    sample = get(endpoint, {"q": "SELECT * FROM public_cases_fc LIMIT 1"})
    fields = [f for f in sample["fields"] if re.search("agency|department|dept|responsible", f, re.I)]
    return {
        "city": "Philadelphia", "endpoint": endpoint,
        "columns": list(sample["fields"]), "agency_fields": fields,
        "values": {f: get(endpoint, {"q": f"SELECT {f}, count(*) AS records FROM public_cases_fc GROUP BY {f} ORDER BY records DESC"}) for f in fields},
    }


def main():
    if "--follow-up" in sys.argv:
        follow_up()
        return
    tasks = [(city, lambda c=city, u=url: gis(c, u)) for city, url in GIS.items()]
    tasks.extend([
        ("Pittsburgh", lambda: ckan("Pittsburgh", "https://data.wprdc.org", "5202679a-d243-402e-b82a-63189995a942")),
        ("Boston", lambda: ckan("Boston", "https://data.boston.gov", "254adca6-64ab-4c5c-9fc0-a6da622be185")),
        ("Philadelphia", philly),
        ("Houston", lambda: files("Houston", "https://hfdapp.houstontx.gov/311/311-CRIS-Public-Data-Extract-D365-MTD-compressed.txt", "|")),
        ("San Diego", lambda: files("San Diego", "https://seshat.datasd.org/get_it_done/get_it_done_requests_open_datasd.csv", ",")),
    ])
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(task): city for city, task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                item = future.result()
            except Exception as exc:
                item = {"city": futures[future], "error": str(exc)}
            results.append(item)
            print(json.dumps(item), flush=True)
            OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def follow_up():
    def houston():
        url = "https://hfdapp.houstontx.gov/311/311-CRIS-Public-Data-Extract-D365-MTD-compressed.txt"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        body = response.content
        if body.startswith(b"\x1f\x8b"):
            body = gzip.decompress(body)
        elif body.startswith(b"PK"):
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                body = archive.read(archive.namelist()[0])
        text = body.decode("utf-8-sig", errors="replace")
        csv.field_size_limit(10000000)
        lines = text.splitlines()
        header_index = next((i for i, line in enumerate(lines) if line.count("|") >= 5 and re.search("department|agency|dept|request|case", line, re.I)), None)
        if header_index is None:
            return {"city": "Houston", "endpoint": url, "header_preview": text[:2500]}
        reader = csv.DictReader(lines[header_index:], delimiter="|")
        fields = [f for f in reader.fieldnames if re.search("agency|department|dept|division|owner", f, re.I)]
        values = {f: set() for f in fields}
        rows = 0
        for row in reader:
            rows += 1
            for field in fields:
                if row.get(field):
                    values[field].add(row[field])
        return {"city": "Houston", "endpoint": url, "columns": reader.fieldnames, "values": {f: sorted(v) for f, v in values.items()}, "rows_reviewed": rows}

    def dc():
        url = GIS["Washington, DC"]
        result = get(url + "/query", {
            "f": "json", "where": "1=1", "outFields": "ORGANIZATIONACRONYM,SERVICETYPECODEDESCRIPTION",
            "returnDistinctValues": "true", "returnGeometry": "false",
        })
        return {"city": "Washington, DC", "endpoint": url, "values": result}

    def denver():
        item = get("https://www.arcgis.com/sharing/rest/content/items/46a685dd1b284ff2a3bf68e062051635", {"f": "json"})
        url = item.get("url", "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_service_requests_311/FeatureServer")
        root = get(url, {"f": "json"})
        layers = root.get("layers", []) + root.get("tables", [])
        if layers:
            return gis("Denver", url + "/" + str(layers[0]["id"]))
        return {"city": "Denver", "item": item, "service": root}

    tasks = [("Houston", houston), ("Washington, DC", dc), ("Denver", denver)]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(task): city for city, task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                item = future.result()
            except Exception as exc:
                item = {"city": futures[future], "error": str(exc)}
            results.append(item)
            Path(__file__).with_name("agency_review_other_followup_evidence.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(item), flush=True)


if __name__ == "__main__":
    main()
