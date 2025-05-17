# backend/app/models/existing.py

from sqlmodel import SQLModel, Field
from typing import Optional
import uuid as uuidlib

class DirectionalSurvey(SQLModel, table=True):
    __tablename__ = "directional_surveys"

    uuid: uuidlib.UUID = Field(default_factory=uuidlib.uuid4, primary_key=True)
    md: Optional[float]
    inc: Optional[float]
    azm: Optional[float]
    b: Optional[float]
    ns: Optional[float]
    ew: Optional[float]
    tvd: Optional[float]
    dls: Optional[float]
    stepout: Optional[float]
    survey: Optional[int]
    api_no: Optional[str]
    well_name: Optional[str]
    lat: Optional[float]
    long: Optional[float]
    operator_name: Optional[str]
