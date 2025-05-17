# app/api/v1/routes/gas_pipeline.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional, Tuple, Literal
import logging
from pydantic import BaseModel, Field

# Import engine functions for gas pipeline calculations
from app.services.hydraulics.engine import (
    calculate_gas_pipeline,
    calculate_gas_pipeline_diameter,
    gas_pipeline_sensitivity,
    calculate_compressor_station,
    design_gas_lift_system,
    design_gas_gathering_system
)

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["gas_pipeline"])

# Define input models
class GasPipelineInput(BaseModel):
    diameter: float = Field(..., gt=0, description="Pipe inside diameter in inches")
    length: float = Field(..., gt=0, description="Pipe length in feet")
    gas_rate: float = Field(..., gt=0, description="Gas flow rate in Mscf/d")
    inlet_pressure: float = Field(..., gt=0, description="Inlet pressure in psia")
    gas_gravity: float = Field(..., gt=0, description="Gas specific gravity (air=1)")
    temperature: float = Field(..., description="Average gas temperature in °F")
    method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth"
    z_factor: Optional[float] = None
    efficiency: float = Field(0.95, gt=0, le=1, description="Pipe efficiency factor (0.5-1.0)")
    elevation_change: float = Field(0.0, description="Elevation change in feet (positive for uphill)")
    co2_fraction: float = Field(0.0, ge=0, le=1, description="CO2 mole fraction")
    h2s_fraction: float = Field(0.0, ge=0, le=1, description="H2S mole fraction")
    n2_fraction: float = Field(0.0, ge=0, le=1, description="N2 mole fraction")

class DiameterInput(BaseModel):
    gas_rate: float = Field(..., gt=0, description="Gas flow rate in Mscf/d")
    length: float = Field(..., gt=0, description="Pipe length in feet")
    inlet_pressure: float = Field(..., gt=0, description="Inlet pressure in psia")
    outlet_pressure: float = Field(..., gt=0, description="Outlet pressure in psia")
    gas_gravity: float = Field(..., gt=0, description="Gas specific gravity (air=1)")
    temperature: float = Field(..., description="Average gas temperature in °F")
    method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth"
    z_factor: Optional[float] = None
    efficiency: float = Field(0.95, gt=0, le=1, description="Pipe efficiency factor (0.5-1.0)")
    velocity_limit: float = Field(60.0, gt=0, description="Maximum allowable velocity (ft/s)")
    available_sizes: Optional[List[float]] = None

class SensitivityInput(BaseModel):
    base_diameter: float = Field(..., gt=0, description="Base pipe diameter in inches")
    base_length: float = Field(..., gt=0, description="Base pipe length in feet")
    base_gas_rate: float = Field(..., gt=0, description="Base gas flow rate in Mscf/d")
    base_inlet_pressure: float = Field(..., gt=0, description="Base inlet pressure in psia")
    gas_gravity: float = Field(..., gt=0, description="Gas specific gravity (air=1)")
    temperature: float = Field(..., description="Average gas temperature in °F")
    method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth"
    variable: Literal["diameter", "length", "flow_rate", "pressure"] = "flow_rate"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    steps: int = Field(10, gt=1, description="Number of steps for sensitivity analysis")
    z_factor: Optional[float] = None
    efficiency: float = Field(0.95, gt=0, le=1, description="Pipe efficiency factor (0.5-1.0)")

class CompressorInput(BaseModel):
    inlet_pressure: float = Field(..., gt=0, description="Inlet pressure in psia")
    outlet_pressure: float = Field(..., gt=0, description="Required outlet pressure in psia")
    gas_rate: float = Field(..., gt=0, description="Gas flow rate in MMscf/d")
    gas_gravity: float = Field(..., gt=0, description="Gas specific gravity (air=1)")
    inlet_temperature: float = Field(..., description="Inlet temperature in °F")
    compressor_type: Literal["centrifugal", "reciprocating"] = "centrifugal"
    max_ratio_per_stage: float = Field(3.0, gt=1, description="Maximum compression ratio per stage")
    efficiency: float = Field(0.75, gt=0, le=1, description="Adiabatic efficiency")
    z_avg: Optional[float] = None
    k: Optional[float] = None

class GasLiftInput(BaseModel):
    wellhead_pressure: float = Field(..., gt=0, description="Wellhead pressure in psia")
    wellhead_temperature: float = Field(..., description="Wellhead temperature in °F")
    gas_injection_depth: float = Field(..., gt=0, description="Gas injection depth in feet")
    liquid_rate: float = Field(..., gt=0, description="Liquid production rate in STB/d")
    water_cut: float = Field(..., ge=0, le=1, description="Water cut as fraction")
    formation_pressure: float = Field(..., gt=0, description="Formation pressure in psia")
    gas_gravity: float = Field(..., gt=0, description="Gas specific gravity (air=1)")
    tubing_id: float = Field(..., gt=0, description="Tubing inner diameter in inches")
    casing_id: float = Field(..., gt=0, description="Casing inner diameter in inches")
    valve_ports: Optional[List[Tuple[float, float]]] = None
    method: str = "beggs-brill"

class WellData(BaseModel):
    id: str
    location: Tuple[float, float]
    gas_rate: float
    pressure: float

class GasGatheringInput(BaseModel):
    well_data: List[WellData]
    central_facility_location: Tuple[float, float]
    pipeline_method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth"
    gas_gravity: float = 0.65
    temperature: float = 80.0
    min_pressure: float = 100.0

# Define API endpoints
@router.post("/calculate")
async def calculate_gas_pipeline_endpoint(data: GasPipelineInput):
    """
    Calculate gas pipeline pressure drop using specified correlation.
    """
    try:
        logger.info(f"Received gas pipeline calculation request using {data.method} method")
        
        result = calculate_gas_pipeline(
            diameter=data.diameter,
            length=data.length,
            gas_rate=data.gas_rate,
            inlet_pressure=data.inlet_pressure,
            gas_gravity=data.gas_gravity,
            temperature=data.temperature,
            method=data.method,
            z_factor=data.z_factor,
            efficiency=data.efficiency,
            elevation_change=data.elevation_change,
            co2_fraction=data.co2_fraction,
            h2s_fraction=data.h2s_fraction,
            n2_fraction=data.n2_fraction
        )
        
        logger.info(f"Gas pipeline calculation completed: pressure_drop={result['pressure_drop']:.2f} psi")
        return result
    
    except Exception as e:
        logger.error(f"Error in gas pipeline calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/diameter")
async def calculate_diameter_endpoint(data: DiameterInput):
    """
    Calculate required pipe diameter for gas pipeline.
    """
    try:
        logger.info(f"Received gas pipeline diameter calculation request using {data.method} method")
        
        result = calculate_gas_pipeline_diameter(
            gas_rate=data.gas_rate,
            length=data.length,
            inlet_pressure=data.inlet_pressure,
            outlet_pressure=data.outlet_pressure,
            gas_gravity=data.gas_gravity,
            temperature=data.temperature,
            method=data.method,
            z_factor=data.z_factor,
            efficiency=data.efficiency,
            available_sizes=data.available_sizes,
            velocity_limit=data.velocity_limit
        )
        
        logger.info(f"Diameter calculation completed: recommended={result['recommended_diameter']:.2f} inches")
        return result
    
    except Exception as e:
        logger.error(f"Error in diameter calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sensitivity")
async def sensitivity_analysis_endpoint(data: SensitivityInput):
    """
    Perform sensitivity analysis on gas pipeline design parameters.
    """
    try:
        logger.info(f"Received sensitivity analysis request for {data.variable}")
        
        result = gas_pipeline_sensitivity(
            base_diameter=data.base_diameter,
            base_length=data.base_length,
            base_gas_rate=data.base_gas_rate,
            base_inlet_pressure=data.base_inlet_pressure,
            gas_gravity=data.gas_gravity,
            temperature=data.temperature,
            method=data.method,
            variable=data.variable,
            min_value=data.min_value,
            max_value=data.max_value,
            steps=data.steps,
            z_factor=data.z_factor,
            efficiency=data.efficiency
        )
        
        logger.info(f"Sensitivity analysis completed with {len(result['results'])} data points")
        return result
    
    except Exception as e:
        logger.error(f"Error in sensitivity analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compressor")
async def compressor_station_endpoint(data: CompressorInput):
    """
    Calculate compressor station requirements for gas pipeline.
    """
    try:
        logger.info(f"Received compressor station calculation request")
        
        result = calculate_compressor_station(
            inlet_pressure=data.inlet_pressure,
            outlet_pressure=data.outlet_pressure,
            gas_rate=data.gas_rate,
            gas_gravity=data.gas_gravity,
            inlet_temperature=data.inlet_temperature,
            compressor_type=data.compressor_type,
            max_ratio_per_stage=data.max_ratio_per_stage,
            efficiency=data.efficiency,
            z_avg=data.z_avg,
            k=data.k
        )
        
        logger.info(f"Compressor calculation completed: power={result['power_required_hp']:.2f} hp")
        return result
    
    except Exception as e:
        logger.error(f"Error in compressor calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/gas-lift")
async def gas_lift_system_endpoint(data: GasLiftInput):
    """
    Design a gas lift system for artificial lift in oil wells.
    """
    try:
        logger.info(f"Received gas lift system design request")
        
        result = design_gas_lift_system(
            wellhead_pressure=data.wellhead_pressure,
            wellhead_temperature=data.wellhead_temperature,
            gas_injection_depth=data.gas_injection_depth,
            liquid_rate=data.liquid_rate,
            water_cut=data.water_cut,
            formation_pressure=data.formation_pressure,
            gas_gravity=data.gas_gravity,
            tubing_id=data.tubing_id,
            casing_id=data.casing_id,
            valve_ports=data.valve_ports,
            method=data.method
        )
        
        logger.info(f"Gas lift design completed: gas_rate={result.get('optimal_gas_rate', 0):.2f} Mscf/d")
        return result
    
    except Exception as e:
        logger.error(f"Error in gas lift system design: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/gathering-system")
async def gas_gathering_system_endpoint(data: GasGatheringInput):
    """
    Design a gas gathering system connecting multiple wells to a central facility.
    """
    try:
        logger.info(f"Received gas gathering system design request for {len(data.well_data)} wells")
        
        result = design_gas_gathering_system(
            well_data=data.well_data,
            central_facility_location=data.central_facility_location,
            pipeline_method=data.pipeline_method,
            gas_gravity=data.gas_gravity,
            temperature=data.temperature,
            min_pressure=data.min_pressure
        )
        
        logger.info(f"Gas gathering system design completed: {len(result['pipelines'])} pipelines")
        return result
    
    except Exception as e:
        logger.error(f"Error in gas gathering system design: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/correlations")
async def get_gas_correlations():
    """
    Get available gas flow correlations for pipeline calculations.
    """
    correlations = [
        {
            "id": "weymouth",
            "name": "Weymouth",
            "description": "For high-pressure gas transmission pipelines with turbulent flow"
        },
        {
            "id": "panhandle_a",
            "name": "Panhandle A",
            "description": "For long-distance gas transmission pipelines with partial turbulence"
        },
        {
            "id": "panhandle_b",
            "name": "Panhandle B",
            "description": "Modern update of Panhandle A for high-pressure gas transmission"
        }
    ]
    
    return {
        "correlations": correlations,
        "recommended_for_gas": "weymouth"
    }

@router.get("/example-input/pipeline")
async def get_example_pipeline_input():
    """
    Return an example input for gas pipeline calculation.
    """
    return GasPipelineInput(
        diameter=12.0,
        length=5280.0,  # 1 mile
        gas_rate=10000.0,  # 10 MMscf/d
        inlet_pressure=1000.0,
        gas_gravity=0.65,
        temperature=80.0,
        method="weymouth",
        efficiency=0.95,
        elevation_change=0.0,
        co2_fraction=0.01,
        h2s_fraction=0.0,
        n2_fraction=0.02
    )

@router.get("/example-input/compressor")
async def get_example_compressor_input():
    """
    Return an example input for compressor calculation.
    """
    return CompressorInput(
        inlet_pressure=500.0,
        outlet_pressure=1200.0,
        gas_rate=10.0,  # 10 MMscf/d
        gas_gravity=0.65,
        inlet_temperature=80.0,
        compressor_type="centrifugal",
        max_ratio_per_stage=3.0,
        efficiency=0.75
    )