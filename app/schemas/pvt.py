# backend/pvt/models.py
from pydantic import BaseModel, Field

class CorrelationOptions(BaseModel):
    pb: str | None = Field(default="standing", description="Bubble point pressure correlation")
    rs: str | None = Field(default="standing", description="Solution gas-oil ratio (Rs) correlation")
    bo: str | None = Field(default="standing", description="Oil formation volume factor (Bo) correlation")
    mu: str | None = Field(default="beggs_robinson", description="Oil viscosity correlation")
    co: str | None = Field(default="vazquez_beggs", description="Oil compressibility correlation")
    rho: str | None = Field(default="standing", description="Oil density correlation")
    z: str | None = Field(default="sutton", description="Gas compressibility factor (Z) correlation")
    ift: str | None = Field(default="asheim", description="Interfacial tension (IFT) correlation")

class PVTInput(BaseModel):
    # Surface/stock tank measurements
    api: float = Field(..., description="Oil API gravity at stock tank")
    gas_gravity: float = Field(..., description="Gas specific gravity (air = 1.0) at stock tank")
    gor: float = Field(..., description="Measured gas-oil ratio (SCF/STB) at stock tank")
    stock_temp: float | None = Field(default=60.0, description="Stock tank temperature (°F)")
    stock_pressure: float | None = Field(default=14.7, description="Stock tank pressure (psia)")

    # Reservoir conditions
    temperature: float = Field(..., description="Reservoir temperature (°F)")
    step_size: int | None = Field(default=25, description="Pressure step size (psi) for curve generation")
    pb: float | None = Field(None, description="Optional bubble point pressure override")

    # Gas composition (mole fraction)
    co2_frac: float | None = Field(default=0.0, description="CO₂ mole fraction")
    h2s_frac: float | None = Field(default=0.0, description="H₂S mole fraction")
    n2_frac: float | None = Field(default=0.0, description="N₂ mole fraction")

    # Method selection
    correlations: dict[str, str] | None = Field(default_factory=dict, description="Correlation method overrides")

    # Optional manual IFT override
    ift: float | None = Field(None, description="User-defined IFT (dyn/cm) override")

class PVTResult(BaseModel):
    z: float = Field(..., description="Gas compressibility factor (Z)")
    bg: float = Field(..., description="Gas formation volume factor (Bg) [RB/SCF]")
    pb: float = Field(..., description="Bubble point pressure (Pb)")
    rs: float = Field(..., description="Solution gas-oil ratio (Rs) [SCF/STB]")
    bo: float = Field(..., description="Oil formation volume factor (Bo) [RB/STB]")
    mu_o: float = Field(..., description="Oil viscosity (μo) [cp]")
    co: float = Field(..., description="Oil compressibility (co) [1/psi]")
    bt: float = Field(..., description="Total formation volume factor (Bt) [RB/STB]")
    rho_o: float = Field(..., description="Oil density at reservoir conditions [lb/ft³]")
    ift: float | None = Field(None, description="Interfacial tension [dynes/cm]")
    pressure: float = Field(..., description="Pressure at which PVT was calculated")