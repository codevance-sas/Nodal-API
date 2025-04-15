from fastapi import FastAPI
from app.api.v1.routes import hydraulics

app = FastAPI(root_path="/api")

app.include_router(hydraulics.router, prefix="/hydraulics")

@app.get("/")
async def root():
    return {"message": "Hello World"}
