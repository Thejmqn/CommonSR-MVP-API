from fastapi import FastAPI, HTTPException
from mangum import Mangum
from requests.exceptions import RequestException

from common_sr import convert_sf_results
from sf311 import fetch_latest_requests

app = FastAPI()
handler = Mangum(app)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}


@app.get("/san-francisco/requests")
def san_francisco_requests():
    """Return the latest 100 SF 311 cases in CommonSR format."""
    try:
        return convert_sf_results(fetch_latest_requests())
    except RequestException as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve SF 311 requests") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Unable to convert SF 311 requests") from exc

# 1. SF - https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/data_preview
# 2. Seattle - https://data.seattle.gov/City-Administration/Customer-Service-Requests/5ngg-rpne/data_preview
# 3. Baton Rouge - https://data.brla.gov/Government/311-Citizen-Requests-for-Service/7ixm-mnvx/data_preview
