# app/schemas/hydraulics.py
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

class GasLiftConfig(BaseModel):
    """Configuration for the gas lift system."""
    enabled: bool = Field(False, description="Set to true to activate gas lift calculation.")
    injection_depth: float = Field(0.0, description="The depth of gas injection, ft.")
    injection_volume_mcfd: float = Field(0.0, description="Total gas volume injected per day, MCFD (frontend sends in thousands).")
    injected_gas_gravity: float = Field(0.65, description="Specific gravity of the injected gas (air=1).")

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
    gas_lift: GasLiftConfig | None = Field(None, description="Gas lift configuration.")

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