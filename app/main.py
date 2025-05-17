from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes import hydraulics, pvt
import time
from app.api.v1.routes import operators
from app.api.v1.routes import wells
from app.api.v1.routes import surveys
from app.api.v1.routes import ipr

app = FastAPI(root_path="/api")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

app.include_router(hydraulics.router, prefix="/hydraulics")
app.include_router(pvt.router, prefix="/pvt")
app.include_router(operators.router, prefix="/operators")
app.include_router(wells.router, prefix="/wells")
app.include_router(surveys.router, prefix="/surveys")
app.include_router(ipr.router, prefix="/ipr")


@app.get("/")
async def root():
    return {"message": "Hello World"}
