# CommonSR Results Specifications
## General Formatting
CommonSR is to return results in JSON formatting, with two main categories: metadata and data. In addition, a list of cities queried will be returned as an array of strings. City names are returned in snake case. The categories are returned as such for a query:
```json
{
    "cities": [],
    "meta": {

    },
    "data": []
}
```
## Metadata results
Within a meta object, a city object is to be returned for each city queried, containing relevant metadata for that city. City names are returned in snake case. For example, if querying for San Francisco, Denver, and Miami, the following meta object is returned:
```json
{
    "san_francisco": {

    },
    "denver": {

    },
    "miami": {

    }
}
```

Metadata fields contain the following information:
* ID - City ID used internally for CommonSR request storage.
* Maintainer - The maintainer(s) of this city's adapter.
* Source - The source link for the original location of the data.
* Agency Mappings - A link to a repository of city agency mappings to generic CommonSR agencies.
* Request Mappings - A link to a repository of city request type mappings to generic CommonSR requests.
* Time Zone - The time zone of the city during standard time.
* Daylight Savings - Boolean value of whether this city follows daylight savings.
* Subdivision 1 - The subdivision type used in the subdivision 1 output.
* Subdivision 2 - The subdivision type used in the subdivision 2 output.
* Subdivision 3 - The subdivision type used in the subdivision 3 output.
* Notes - Additional notes for usage of the city's data. Formatted as an array of relevant string notes.

Example for San Francisco:
```json
{
    "id": 1,
    "maintainer": "https://github.com/Thejmqn",
    "source": "https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/about_data",
    "agency_mappings": "https://www.servicerequest.org/agency-mappings/1",
    "request_mappings": "https://www.servicerequest.org/request-mappings/1",
    "time_zone": "PST",
    "daylight_savings": true,
    "sub_1": "Supervisor District",
    "sub_2": "Neighborhood",
    "sub_3": "Police District",
    "notes": ""
    
}
```

## Data results
Within a data object, the following fields shall be provided for all cities adapted to the CommonSR format:
* ID - Unique city-wide ID of the service request. Guarenteed to be unique relative to other service requests from the same city, but not compared to other cities. 
* Status - A string value of either "open", "in_progress", "resolved", or "rejected"
* Opened - An object with two fields, Local and UTC. The Local field contains the date and time of the service request opening, formatted accorded to ISO8601 in the local time zone. The UTC contains the same, but output in UTC. 
* Modified - An object with two fields, Local and UTC. The Local field contains the date and time of the last modification of the service request, formatted accorded to ISO8601 in the local time zone. The UTC contains the same, but output in UTC. 
* Closed - Null if service request status is "Open" or "In Progress". Otherwise, an object with two fields, Local and UTC. The Local field contains the date and time of the service request closing, formatted accorded to ISO8601 in the local time zone. The UTC contains the same, but output in UTC. 
* Address - The street address of the service request.
* Latitude - Up to 8 decimal places of precision of the latitude of the service request.
* Longitutde - Up to 8 decimal places of precision of the longitude of the service request.
* Subdivision 1 - As defined in the city metadata field, the first type of subdivision the location of this service request belongs to. If none exists, this value is null.
* Subdivision 2 - As defined in the city metadata field, the first type of subdivision the location of this service request belongs to. If none exists, this value is null.
* Subdivision 3 - As defined in the city metadata field, the first type of subdivision the location of this service request belongs to. If none exists, this value is null.
* Agency - An object with two fields, raw and clean. The raw field is the name of the responsible agency as listed in the original request, while the clean is a simplified, cross-city version of the agency's role.
* Request - An object with two fields, raw and clean. The raw field is the details of the service request as listed in the original request, while the clean is a simplified, cross-city version of the request.
* Description - Any extra details, comments, or descriptions included in the request which do not fit cleanly in another category. This field will not be editted from the original service request data. May be null if no applicable category exists, or the empty string if an applicable category exists, but no additional information was provided. 

An example response template from the City of San Francisco is given below:
```json
{
    "id": "202000356430",
    "status": "resolved",
    "opened": {
        "local": "2026-11-25T19:58:36-08:00",
        "utc": "2026-11-26T03:58:36Z"
    },
    "modified": {
        "local": "2026-11-25T21:02:37-08:00",
        "utc": "2026-11-26T05:02:37Z"
    },
    "closed": {
        "local": "2026-11-25T21:02:37-08:00",
        "utc": "2026-11-26T05:02:37Z"
    },
    "address": "11 TIOGA AVE, SAN FRANCISCO, CA 94134, US",
    "latitude": 37.71561113,
    "longitude": -122.40314051,
    "sub_1": "10",
    "sub_2": "Visitacion Valley",
    "sub_3": "INGLESIDE",
    "agency": {
        "raw": "MTA - Parking Enforcement Dispatch",
        "clean": "Transportation"
    },
    "request": {
        "raw": "Parking Enforcement - blocking_driveway_cite_tow",
        "clean": "Illegal Parking"
    },
    "description": ""
}
```
