# CommonSR API

Install dependencies with `py -3.12 -m pip install -r requirements.txt`.

## San Francisco 311 requests

Live requests require a valid Socrata application token in the `SOCOTRA_SECRET`
environment variable. The converter can read saved records without a token.

Run `py -3.12 sf311.py` to save the latest 100 cases to
`sf_311_common_sr.json`, or specify a path with `--output`.
The FastAPI application also exposes `GET /san-francisco/requests` with the
same CommonSR response containing `cities`, `meta`, and `data`.

Convert a previously retrieved raw JSON array without network access:

```powershell
py -3.12 sf311.py --input sf_311_latest_100.json
```

The converter follows [the CommonSR specification](Specifications/query_results.md).
SF `Open` and `Closed` statuses become `open` and `resolved`. Timestamps
include SF local offsets and UTC values using `America/Los_Angeles` daylight
saving rules. Coordinates are numeric with at most eight decimal places.
Supervisor District, SF Find Neighborhood, and Police District populate
`sub_1`, `sub_2`, and `sub_3`; absent subdivisions are null.
`service_details` supplies `description` (null when absent or empty).
Each record includes `agency.raw` from `agency_responsible` and `agency.clean`
from [the SF mappings CSV](Specifications/san_francisco_agency_mappings.csv).
Exact raw names are preserved and matched, including historical queue names.
All CSV assignments are applied, including rows flagged for later review.
Unknown or missing agencies have a null `clean` value; a missing raw agency
also has a null `raw` value.
Each record includes `request.raw` as the SF service name and subtype joined
with ` - `. When only one value exists, the converter uses that value alone.
`request.clean` comes from the San Francisco pairs in the
[request-type evidence](research/common_sr_request_type_evidence.json).
The lookup ignores casing and surrounding whitespace and recognizes a few
equivalent SF label pairs. Unmapped pairs have a null `clean` value.
The converter reads both mapping files once per batch. Include the agency
CSV and request evidence JSON at their repository paths when packaging the
API, including for Lambda.
Metadata uses the SF values from the specification, with `notes` as an array
as required by its field definition. Mapping URLs are metadata from the
specification. The converter reads the local mapping files.

Run converter tests with `py -3.12 -m unittest discover -s tests`.

“Latest” means the most recently opened cases (`requested_datetime`), with
`service_request_id` descending as a tiebreaker. The query excludes missing
opening dates and limits the response to 100 rows on the server.

The script uses `requests.post` with the [SODA 3.0 query endpoint](https://data.sf.gov/api/v3/views/vw6y-z8j6/query.json).
It sends the [SoQL query](https://dev.socrata.com/docs/queries/) in the JSON
body and the token in the `X-App-Token` header.
