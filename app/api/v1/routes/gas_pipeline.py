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
    
    This endpoint calculates the pressure drop in a gas pipeline using the specified correlation method.
    It accounts for pipe diameter, length, gas properties, and operating conditions to determine
    outlet pressure, flow velocity, and other parameters.
    
    Available correlation methods include:
    - weymouth: For high-pressure gas transmission pipelines with turbulent flow
    - panhandle_a: For long-distance gas transmission pipelines with partial turbulence
    - panhandle_b: Modern update of Panhandle A for high-pressure gas transmission
    
    Parameters:
    - data: Input data containing:
      - diameter: Pipe inside diameter in inches
      - length: Pipe length in feet
      - gas_rate: Gas flow rate in Mscf/d
      - inlet_pressure: Inlet pressure in psia
      - gas_gravity: Gas specific gravity (air=1)
      - temperature: Average gas temperature in °F
      - method: Correlation method to use (default: "weymouth")
      - z_factor: Gas compressibility factor (optional)
      - efficiency: Pipe efficiency factor (0.5-1.0, default: 0.95)
      - elevation_change: Elevation change in feet, positive for uphill (default: 0.0)
      - co2_fraction: CO2 mole fraction (default: 0.0)
      - h2s_fraction: H2S mole fraction (default: 0.0)
      - n2_fraction: N2 mole fraction (default: 0.0)
    
    Returns:
    - A dictionary containing:
      - inlet_pressure: Inlet pressure in psia
      - outlet_pressure: Calculated outlet pressure in psia
      - pressure_drop: Pressure drop in psi
      - flow_velocity: Gas velocity in ft/s
      - reynolds_number: Reynolds number
      - friction_factor: Darcy-Weisbach friction factor
      - flow_regime: Flow regime (e.g., "Turbulent")
      - z_factor: Gas compressibility factor
      - is_valid: Whether the calculation is valid
      - max_flow: Maximum flow rate (if calculation is invalid)
    
    Example response:
    ```json
    {
      "inlet_pressure": 1000.0,
      "outlet_pressure": 856.3,
      "pressure_drop": 143.7,
      "flow_velocity": 15.2,
      "reynolds_number": 4.5e6,
      "friction_factor": 0.0185,
      "flow_regime": "Turbulent",
      "z_factor": 0.92,
      "is_valid": true,
      "diameter": 12.0,
      "length": 5280.0,
      "gas_rate": 10000.0,
      "gas_gravity": 0.65,
      "method": "weymouth",
      "elevation_change": 0.0
    }
    ```
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
    
    This endpoint calculates the minimum required pipe diameter for a gas pipeline
    based on the specified flow rate, pressure conditions, and correlation method.
    It also recommends a standard pipe size from available options and checks
    velocity constraints.
    
    Available correlation methods include:
    - weymouth: For high-pressure gas transmission pipelines with turbulent flow
    - panhandle_a: For long-distance gas transmission pipelines with partial turbulence
    - panhandle_b: Modern update of Panhandle A for high-pressure gas transmission
    
    Parameters:
    - data: Input data containing:
      - gas_rate: Gas flow rate in Mscf/d
      - length: Pipe length in feet
      - inlet_pressure: Inlet pressure in psia
      - outlet_pressure: Outlet pressure in psia
      - gas_gravity: Gas specific gravity (air=1)
      - temperature: Average gas temperature in °F
      - method: Correlation method to use (default: "weymouth")
      - z_factor: Gas compressibility factor (optional)
      - efficiency: Pipe efficiency factor (0.5-1.0, default: 0.95)
      - velocity_limit: Maximum allowable velocity in ft/s (default: 60.0)
      - available_sizes: Optional list of available pipe sizes in inches
    
    Returns:
    - A dictionary containing:
      - calculated_diameter: Theoretical calculated diameter in inches
      - recommended_diameter: Recommended standard pipe size in inches
      - velocity: Gas velocity at recommended diameter in ft/s
      - velocity_ok: Whether the velocity is within limits
      - pressure_drop: Pressure drop at recommended diameter in psi
      - available_sizes: List of available pipe sizes that were considered
      - flow_regime: Flow regime at recommended diameter
      - reynolds_number: Reynolds number at recommended diameter
    
    Example response:
    ```json
    {
      "calculated_diameter": 10.47,
      "recommended_diameter": 12.0,
      "velocity": 42.3,
      "velocity_ok": true,
      "pressure_drop": 143.7,
      "available_sizes": [2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0],
      "flow_regime": "Turbulent",
      "reynolds_number": 3.8e6
    }
    ```
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
    
    This endpoint analyzes how changes in a selected variable (diameter, length, flow rate, or pressure)
    affect the gas pipeline performance. This is useful for:
    - Optimizing pipeline design
    - Understanding operational limits
    - Evaluating the impact of changing conditions
    - Planning for future capacity requirements
    
    Available correlation methods include:
    - weymouth: For high-pressure gas transmission pipelines with turbulent flow
    - panhandle_a: For long-distance gas transmission pipelines with partial turbulence
    - panhandle_b: Modern update of Panhandle A for high-pressure gas transmission
    
    Parameters:
    - data: Input data containing:
      - base_diameter: Base pipe diameter in inches
      - base_length: Base pipe length in feet
      - base_gas_rate: Base gas flow rate in Mscf/d
      - base_inlet_pressure: Base inlet pressure in psia
      - gas_gravity: Gas specific gravity (air=1)
      - temperature: Average gas temperature in °F
      - method: Correlation method to use (default: "weymouth")
      - variable: Variable to analyze ("diameter", "length", "flow_rate", or "pressure")
      - min_value: Minimum value for the variable (optional)
      - max_value: Maximum value for the variable (optional)
      - steps: Number of steps for sensitivity analysis (default: 10)
      - z_factor: Gas compressibility factor (optional)
      - efficiency: Pipe efficiency factor (0.5-1.0, default: 0.95)
    
    Returns:
    - A dictionary containing:
      - base_case: Results for the base case
      - variable: The variable that was analyzed
      - results: Array of results for each value of the variable
      - summary: Summary statistics and trends
    
    Example response for variable="diameter":
    ```json
    {
      "base_case": {
        "diameter": 12.0,
        "outlet_pressure": 856.3,
        "pressure_drop": 143.7
      },
      "variable": "diameter",
      "results": [
        {
          "diameter": 8.0,
          "outlet_pressure": 723.5,
          "pressure_drop": 276.5,
          "flow_velocity": 34.2
        },
        {
          "diameter": 12.0,
          "outlet_pressure": 856.3,
          "pressure_drop": 143.7,
          "flow_velocity": 15.2
        },
        {
          "diameter": 16.0,
          "outlet_pressure": 912.8,
          "pressure_drop": 87.2,
          "flow_velocity": 8.5
        }
      ],
      "summary": {
        "optimal_value": 14.0,
        "pressure_drop_trend": "decreasing",
        "velocity_trend": "decreasing"
      }
    }
    ```
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
    
    This endpoint calculates the compressor station requirements for a gas pipeline,
    including power requirements, number of stages, compression ratios, and discharge
    temperatures. This is useful for:
    - Designing compressor stations
    - Estimating power requirements and fuel consumption
    - Optimizing compression stages
    - Evaluating different compressor types
    
    Parameters:
    - data: Input data containing:
      - inlet_pressure: Inlet pressure in psia
      - outlet_pressure: Required outlet pressure in psia
      - gas_rate: Gas flow rate in MMscf/d
      - gas_gravity: Gas specific gravity (air=1)
      - inlet_temperature: Inlet temperature in °F
      - compressor_type: Type of compressor ("centrifugal" or "reciprocating")
      - max_ratio_per_stage: Maximum compression ratio per stage (default: 3.0)
      - efficiency: Adiabatic efficiency (0-1, default: 0.75)
      - z_avg: Average compressibility factor (optional)
      - k: Specific heat ratio (optional)
    
    Returns:
    - A dictionary containing:
      - power_required_hp: Total power required in horsepower
      - power_required_kw: Total power required in kilowatts
      - number_of_stages: Optimal number of compression stages
      - stage_details: Array with details for each compression stage
      - compression_ratio: Overall compression ratio
      - fuel_consumption: Estimated fuel consumption
      - discharge_temperature: Final discharge temperature in °F
    
    Example response:
    ```json
    {
      "power_required_hp": 4256.8,
      "power_required_kw": 3175.0,
      "number_of_stages": 3,
      "stage_details": [
        {
          "stage": 1,
          "inlet_pressure": 500.0,
          "outlet_pressure": 750.0,
          "compression_ratio": 1.5,
          "power_hp": 1245.6,
          "discharge_temperature": 145.2
        },
        {
          "stage": 2,
          "inlet_pressure": 750.0,
          "outlet_pressure": 1000.0,
          "compression_ratio": 1.33,
          "power_hp": 1356.7,
          "discharge_temperature": 138.5
        },
        {
          "stage": 3,
          "inlet_pressure": 1000.0,
          "outlet_pressure": 1200.0,
          "compression_ratio": 1.2,
          "power_hp": 1654.5,
          "discharge_temperature": 132.8
        }
      ],
      "compression_ratio": 2.4,
      "fuel_consumption": 0.35,
      "discharge_temperature": 132.8,
      "z_avg": 0.92,
      "k": 1.32
    }
    ```
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
    
    This endpoint designs a gas lift system for artificial lift in oil wells,
    calculating the optimal gas injection rate, valve placement, and pressure requirements.
    This is useful for:
    - Designing new gas lift installations
    - Optimizing existing gas lift systems
    - Evaluating artificial lift options
    - Predicting production improvements from gas lift
    
    Parameters:
    - data: Input data containing:
      - wellhead_pressure: Wellhead pressure in psia
      - wellhead_temperature: Wellhead temperature in °F
      - gas_injection_depth: Gas injection depth in feet
      - liquid_rate: Liquid production rate in STB/d
      - water_cut: Water cut as fraction (0-1)
      - formation_pressure: Formation pressure in psia
      - gas_gravity: Gas specific gravity (air=1)
      - tubing_id: Tubing inner diameter in inches
      - casing_id: Casing inner diameter in inches
      - valve_ports: Optional list of valve port depths and sizes as tuples (depth, size)
      - method: Multiphase flow correlation method (default: "beggs-brill")
    
    Returns:
    - A dictionary containing:
      - optimal_gas_rate: Optimal gas injection rate in Mscf/d
      - valve_design: Array with details for each gas lift valve
      - pressure_profile: Pressure profile in the tubing
      - production_increase: Estimated production increase
      - operating_envelope: Operating envelope for the gas lift system
      - surface_requirements: Surface equipment requirements
    
    Example response:
    ```json
    {
      "optimal_gas_rate": 1250.0,
      "valve_design": [
        {
          "depth": 8000.0,
          "port_size": 0.25,
          "opening_pressure": 1200.0,
          "closing_pressure": 1150.0,
          "gas_passage": 0.5
        },
        {
          "depth": 6000.0,
          "port_size": 0.25,
          "opening_pressure": 1000.0,
          "closing_pressure": 950.0,
          "gas_passage": 0.75
        }
      ],
      "pressure_profile": {
        "depths": [0, 2000, 4000, 6000, 8000],
        "pressures": [500, 750, 1000, 1250, 1500]
      },
      "production_increase": {
        "before": 500.0,
        "after": 800.0,
        "percent_increase": 60.0
      },
      "operating_envelope": {
        "min_gas_rate": 800.0,
        "max_gas_rate": 1500.0,
        "min_pressure": 900.0,
        "max_pressure": 1400.0
      },
      "surface_requirements": {
        "compressor_power": 250.0,
        "gas_supply": 1.5
      }
    }
    ```
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
    
    This endpoint designs an optimal gas gathering system that connects multiple wells
    to a central processing facility. It determines the pipeline network layout,
    pipe sizes, and pressure requirements. This is useful for:
    - Field development planning
    - Gathering system design and optimization
    - Capital expenditure estimation
    - Production system capacity planning
    
    Parameters:
    - data: Input data containing:
      - well_data: List of well data objects, each containing:
        - id: Well identifier
        - location: Well location as (latitude, longitude) tuple
        - gas_rate: Gas production rate in Mscf/d
        - pressure: Wellhead pressure in psia
      - central_facility_location: Location of central facility as (latitude, longitude) tuple
      - pipeline_method: Correlation method to use (default: "weymouth")
      - gas_gravity: Gas specific gravity (air=1, default: 0.65)
      - temperature: Average gas temperature in °F (default: 80.0)
      - min_pressure: Minimum required pressure at central facility in psia (default: 100.0)
    
    Returns:
    - A dictionary containing:
      - pipelines: Array of pipeline segments in the gathering system
      - total_length: Total length of all pipelines in feet
      - total_cost: Estimated total cost of the gathering system
      - pressure_summary: Pressure details at key points in the system
      - material_summary: Summary of pipe materials and sizes required
      - optimization_metrics: Metrics used for optimization
    
    Example response:
    ```json
    {
      "pipelines": [
        {
          "from": "Well-A",
          "to": "Node-1",
          "length": 5280.0,
          "diameter": 6.0,
          "flow_rate": 2000.0,
          "inlet_pressure": 800.0,
          "outlet_pressure": 750.0
        },
        {
          "from": "Well-B",
          "to": "Node-1",
          "length": 3520.0,
          "diameter": 4.0,
          "flow_rate": 1500.0,
          "inlet_pressure": 850.0,
          "outlet_pressure": 750.0
        },
        {
          "from": "Node-1",
          "to": "Central",
          "length": 7920.0,
          "diameter": 8.0,
          "flow_rate": 3500.0,
          "inlet_pressure": 750.0,
          "outlet_pressure": 650.0
        }
      ],
      "total_length": 16720.0,
      "total_cost": 1250000.0,
      "pressure_summary": {
        "highest_pressure": 850.0,
        "lowest_pressure": 650.0,
        "central_facility_pressure": 650.0
      },
      "material_summary": {
        "4_inch": 3520.0,
        "6_inch": 5280.0,
        "8_inch": 7920.0
      },
      "optimization_metrics": {
        "algorithm": "minimum spanning tree",
        "iterations": 5,
        "objective_function": "minimize_cost"
      }
    }
    ```
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
    
    This endpoint returns a list of available gas flow correlations that can be used
    with the gas pipeline calculation endpoints. Each correlation is specialized for
    certain pipeline conditions and flow regimes.
    
    No parameters are required for this endpoint.
    
    Returns:
    - A dictionary containing:
      - correlations: Array of correlation objects, each containing:
        - id: Correlation identifier to use in API requests
        - name: Human-readable name of the correlation
        - description: Description of when the correlation is applicable
      - recommended_for_gas: The recommended correlation for general gas pipeline calculations
    
    Example response:
    ```json
    {
      "correlations": [
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
      ],
      "recommended_for_gas": "weymouth"
    }
    ```
    
    These correlation IDs can be used in the "method" field of the input data for
    the /calculate, /diameter, and /sensitivity endpoints.
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
    
    This endpoint provides a complete example of the input data structure required
    for the /calculate endpoint. This is useful for:
    - Understanding the required input format
    - Testing the API
    - Creating templates for your own calculations
    
    No parameters are required for this endpoint.
    
    Returns:
    - A complete GasPipelineInput object with sample values for all fields
    
    Example response:
    ```json
    {
      "diameter": 12.0,
      "length": 5280.0,
      "gas_rate": 10000.0,
      "inlet_pressure": 1000.0,
      "gas_gravity": 0.65,
      "temperature": 80.0,
      "method": "weymouth",
      "efficiency": 0.95,
      "elevation_change": 0.0,
      "co2_fraction": 0.01,
      "h2s_fraction": 0.0,
      "n2_fraction": 0.02
    }
    ```
    
    You can use this example as a starting point and modify the values as needed
    for your specific pipeline conditions. The example uses the Weymouth correlation,
    but you can change the "method" field to "panhandle_a" or "panhandle_b" to use
    other correlations.
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
    
    This endpoint provides a complete example of the input data structure required
    for the /compressor endpoint. This is useful for:
    - Understanding the required input format
    - Testing the API
    - Creating templates for your own calculations
    
    No parameters are required for this endpoint.
    
    Returns:
    - A complete CompressorInput object with sample values for all fields
    
    Example response:
    ```json
    {
      "inlet_pressure": 500.0,
      "outlet_pressure": 1200.0,
      "gas_rate": 10.0,
      "gas_gravity": 0.65,
      "inlet_temperature": 80.0,
      "compressor_type": "centrifugal",
      "max_ratio_per_stage": 3.0,
      "efficiency": 0.75
    }
    ```
    
    You can use this example as a starting point and modify the values as needed
    for your specific compressor station requirements. The example uses a centrifugal
    compressor, but you can change the "compressor_type" field to "reciprocating"
    to use a different compressor type.
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