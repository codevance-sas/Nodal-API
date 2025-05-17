# app/schemas/ipr.py
from pydantic import BaseModel, Field

class IPRInput(BaseModel):
    """
    Input model for IPR calculations
    """
    BOPD: float = Field(..., description="Oil flow rate (barrels of oil per day)")
    BWPD: float = Field(..., description="Water flow rate (barrels of water per day)")
    MCFD: float = Field(..., description="Gas flow rate (thousand cubic feet per day)")
    Pr: float = Field(..., description="Reservoir pressure (psia)")
    Pb: float | None = Field(None, description="Bubble point pressure (psia)")
    PIP: float = Field(..., description="Pump intake pressure (psia)")
    steps: int = Field(25, description="Number of calculation steps")
    
class IPRResult(BaseModel):
    """
    Output model for IPR calculation results
    """
    ipr_curve: list
    nodal_points: list
    productivity_index: float
    params: dict