from sqlmodel import SQLModel, Field
import uuid

class Operator(SQLModel, table=True):
    __tablename__ = "operators"
    
    id: int = Field(primary_key=True)
    operator_name: str = Field(max_length=255)

class Well(SQLModel, table=True):
    __tablename__ = "wells"
    
    id: str = Field(primary_key=True)
    well_name: str = Field(max_length=255)
    longitude: float
    latitude: float
    operator_id: int = Field(foreign_key="operators.id")

class Survey(SQLModel, table=True):
    __tablename__ = "surveys"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    well_id: str = Field(foreign_key="wells.id")
    survey: int
    md: float
    inc: float
    azm: float
    b: float
    rf: float
    ns: float
    ew: float
    tvd: float
    dls: float
    stepout: float
    