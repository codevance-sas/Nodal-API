from fastapi import FastAPI
from app.api.v1.routes import hydraulics, pvt

app = FastAPI(root_path="/api")

app.include_router(hydraulics.router, prefix="/hydraulics")
app.include_router(pvt.router, prefix="/pvt")

@app.get("/")
async def root():
    return {"message": "Hello World"}
