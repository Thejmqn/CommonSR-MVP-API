from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()
handler = Mangum(app)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

# 1. SF - https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/data_preview
# 2. Seattle - https://data.seattle.gov/City-Administration/Customer-Service-Requests/5ngg-rpne/data_preview
# 3. Baton Rouge - https://data.brla.gov/Government/311-Citizen-Requests-for-Service/7ixm-mnvx/data_preview
