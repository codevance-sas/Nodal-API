# app/schemas/hydraulicsV2.py
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal
from enum import Enum


class FlowPatternEnum(str, Enum):
    BUBBLE = "bubble"
    SLUG = "slug"
    TRANSITION = "transition"
    ANNULAR = "annular"
    STRATIFIED = "stratified"
    WAVY = "wavy"
    MIST = "mist"
    

class FluidPropertiesInput(BaseModel):
    oil_rate: float = Field(..., description="Oil flow rate, STB/d")
    water_rate: float = Field(..., description="Water flow rate, STB/d")
    gas_rate: float = Field(..., description="Gas flow rate, Mscf/d")
    oil_gravity: float = Field(..., description="Oil gravity, °API")
    water_gravity: float = Field(1.0, description="Water specific gravity")
    gas_gravity: float = Field(..., description="Gas specific gravity (air=1)")
    bubble_point: float = Field(..., description="Bubble point pressure, psia")
    temperature_gradient: float = Field(..., description="Temperature gradient, °F/ft")
    surface_temperature: float = Field(..., description="Surface temperature, °F")
    wct: Optional[float] = Field(None, description="Water cut, fraction")
    gor: Optional[float] = Field(None, description="Gas-oil ratio, scf/STB")
    glr: Optional[float] = Field(None, description="Gas-liquid ratio, scf/STB")

class PipeSegment(BaseModel):
    start_depth: float = Field(..., description="Start depth of the segment, ft")
    end_depth: float = Field(..., description="End depth of the segment, ft")
    diameter: float = Field(..., description="Diameter of the segment, in")
    
class WellboreGeometryInput(BaseModel):
    pipe_segments: List[PipeSegment] = Field(..., description="List of pipe segments")
    deviation: float = Field(0.0, description="Well deviation from vertical, degrees")
    roughness: float = Field(0.0006, description="Pipe roughness, in")
    depth_steps: int = Field(100, description="Number of calculation steps")

class SurveyData(BaseModel):
    md: float = Field(..., description="Measured depth of the survey, ft")
    tvd: float = Field(..., description="True vertical depth at the survey depth, ft")
    inclination: float = Field(..., description="Inclination at the survey depth, degrees")


class GasLiftValve:
    md: float                              # Measured depth of the valve [ft]
    type: str = "ORIFICE"                  # "ORIFICE" | "IPO" | "PPO" (Future)
    port_diameter: float = 0.125           # Orifice diameter [in]
    Cd: float = 0.85                       # Discharge coefficient [-]
    delta_p_min: float = 0.0               # Minimum ΔP to start injecting [psia]
    activation_window_md: float = 5.0      # Activation tolerance around MD [ft]
    max_rate_per_valve_mscfd: float = 1e9  # Valve-level cap [scf/d] (optional)
    flow_coeff_to_scfpd: float = 1.0       # Dimensional fix if needed
    valve_curve: Optional[List[tuple]] = None  # [(dp_psia, q_scfpd), ...] (optional)
    gas_source: str = "ANNULUS"            # Placeholder for future routing
    status: str = "OPERATING"              # "OPERATING" | "UNLOADING" | "DUMMY"

class GasLiftConfig:
    enabled: bool = False
    gas_sg: float = 0.65                   # Specific gravity of injection gas (air=1)
    gas_composition: Optional[dict] = None # If you plan to run EoS mixing later
    z_model: str = "Standing"              # "DAK" | "PR" | "BWRS" | "Standing"
    surface_annulus_pressure: float = 0.0  # Casinghead pressure [psia]
    annulus_pressure_profile: Optional[List[tuple]] = None  # [(md_ft, psia), ...]
    t_annulus_injection: float = 120.0     # Annulus gas temperature [°F]
    max_total_injection_mscfd: Optional[float] = None  # Plant/supply cap [scf/d]
    valves: List[GasLiftValve] = []

class HydraulicsInput(BaseModel):
    fluid_properties: FluidPropertiesInput
    wellbore_geometry: WellboreGeometryInput
    method: Literal[
        "hagedorn-brown", 
        "beggs-brill", 
        "duns-ross", 
        "chokshi",
        "orkiszewski",
        "gray",
        "mukherjee-brill",
        "aziz",
        "hasan-kabir",
        "ansari"
    ] = "hagedorn-brown"
    surface_pressure: float = Field(..., description="Surface pressure, psia")
    bhp_mode: Literal["calculate", "target"] = "calculate"
    target_bhp: Optional[float] = Field(None, description="Target bottomhole pressure, psia")
    survey_data: Optional[List[SurveyData]] = Field(None, description="Survey data")
    gas_lift: Optional[GasLiftConfig] = None

class FlowPatternResult(BaseModel):
    depth: float
    flow_pattern: FlowPatternEnum
    liquid_holdup: float
    mixture_velocity: float
    superficial_liquid_velocity: float
    superficial_gas_velocity: float
    

class PressurePoint(BaseModel):
    depth: float
    pressure: float
    temperature: float
    flow_pattern: Optional[FlowPatternEnum] = None
    liquid_holdup: Optional[float] = None
    mixture_density: Optional[float] = None
    mixture_velocity: Optional[float] = None
    reynolds_number: Optional[float] = None
    friction_factor: Optional[float] = None
    dpdz_elevation: Optional[float] = None
    dpdz_friction: Optional[float] = None
    dpdz_acceleration: Optional[float] = None
    dpdz_total: Optional[float] = None


class HydraulicsResult(BaseModel):
    method: str
    pressure_profile: List[PressurePoint]
    surface_pressure: float
    bottomhole_pressure: float
    overall_pressure_drop: float
    elevation_drop_percentage: float
    friction_drop_percentage: float
    acceleration_drop_percentage: float
    flow_patterns: List[FlowPatternResult]


class FlowRateInput(BaseModel):
    min_oil_rate: float = Field(..., description="Minimum oil rate to evaluate, STB/d")
    max_oil_rate: float = Field(..., description="Maximum oil rate to evaluate, STB/d")
    steps: int = Field(10, description="Number of steps between min and max")
    water_cut: float = Field(0.0, description="Water cut, fraction")
    gor: float = Field(..., description="Gas-oil ratio, scf/STB")
    base_data: HydraulicsInput = Field(..., description="Base input data")


class GeometryInput(BaseModel):
    min_tubing_id: float = Field(..., description="Minimum tubing ID to evaluate, inches")
    max_tubing_id: float = Field(..., description="Maximum tubing ID to evaluate, inches")
    steps: int = Field(10, description="Number of steps between min and max")
    base_data: HydraulicsInput = Field(..., description="Base input data")