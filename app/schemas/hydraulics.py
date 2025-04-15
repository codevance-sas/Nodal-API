# backend/hydraulics/models.py
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
    wct: float | None = Field(None, description="Water cut, fraction")
    gor: float | None = Field(None, description="Gas-oil ratio, scf/STB")
    glr: float | None = Field(None, description="Gas-liquid ratio, scf/STB")

class WellboreGeometryInput(BaseModel):
    depth: float = Field(..., description="Well depth, ft")
    deviation: float = Field(0.0, description="Well deviation from vertical, degrees")
    tubing_id: float = Field(..., description="Tubing inner diameter, in")
    casing_id: float | None = Field(None, description="Casing inner diameter, in")
    roughness: float = Field(0.0006, description="Pipe roughness, in")
    depth_steps: int = Field(100, description="Number of calculation steps")

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
    target_bhp: float | None = Field(None, description="Target bottomhole pressure, psia")
    
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
    flow_pattern: FlowPatternEnum | None = None
    liquid_holdup: float | None = None
    mixture_density: float | None = None
    mixture_velocity: float | None = None
    reynolds_number: float | None = None
    friction_factor: float | None = None
    dpdz_elevation: float | None = None
    dpdz_friction: float | None = None
    dpdz_acceleration: float | None = None
    dpdz_total: float | None = None

class HydraulicsResult(BaseModel):
    method: str
    pressure_profile: list[PressurePoint]
    surface_pressure: float
    bottomhole_pressure: float
    overall_pressure_drop: float
    elevation_drop_percentage: float
    friction_drop_percentage: float
    acceleration_drop_percentage: float
    flow_patterns: list[FlowPatternResult]