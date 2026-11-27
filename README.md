# CommonSR API

Install dependencies with `py -3.12 -m pip install -r requirements.txt`.

## San Francisco 311 requests

Set the `SOCOTRA_SECRET` environment variable to your Socrata application token.
The token is read at runtime and is never saved in the results. If it is absent,
the script uses public, unauthenticated access, which has lower rate limits.

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
`status_notes` is preserved verbatim as `description` (null when absent).
Data records omit `agency` and `request` until mappings are implemented.
Metadata uses the SF values from the specification, with `notes` as an array
as required by its field definition. Mapping URLs are metadata from the
specification; the converter does not fetch or apply them.

Run converter tests with `py -3.12 -m unittest discover -s tests`.

“Latest” means the most recently opened cases (`requested_datetime`), with
`service_request_id` descending as a tiebreaker. The query excludes missing
opening dates and limits the response to 100 rows on the server.

The [dataset](https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/data_preview)
also exposes a v3 query endpoint. The requested
[sodapy package](https://pypi.org/project/sodapy/) uses the compatible SODA
resource endpoint, `https://data.sf.gov/resource/vw6y-z8j6.json`, and sends
the [SoQL query](https://dev.socrata.com/docs/queries/) as `$query`.
