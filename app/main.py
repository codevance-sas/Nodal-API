from fastapi import FastAPI, Depends, Request
from app.api.v1.routes import hydraulics, pvt
from app.db.session import session
from app.models.survey import Operator, Well
from sqlmodel import select
from sqlalchemy.orm import Session
import time

app = FastAPI(root_path="/api")

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

app.include_router(hydraulics.router, prefix="/hydraulics")
app.include_router(pvt.router, prefix="/pvt")

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/operators")
async def operators(session: Session = Depends(session)):
    result = session.exec(select(Operator)).all()
    return {"message": result}

@app.get("/wells")
async def wells(session: Session = Depends(session)):
    result = session.exec(select(Well)).all()
    return {"message": result}
