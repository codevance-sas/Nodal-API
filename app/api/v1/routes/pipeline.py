# app/api/v1/routes/pipeline.py

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging

# Import your existing hydraulics services
from app.services.hydraulics.engine import calculate_hydraulics
from app.services.hydraulics.funcs import available_methods
from app.services.hydraulics.extensions.pipeline import (
    adapt_hydraulics_input_for_pipeline,
    adapt_hydraulics_output_for_pipeline
)

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["pipeline"])

# Simple models directly in this file - in the future, move these to schemas directory
from pydantic import BaseModel, Field

class PipelinePoint(BaseModel):
    id: str
    latitude: float
    longitude: float
    elevation: float = 0  # feet
    name: Optional[str] = None
    flowrate: Optional[float] = None  # STB/d
    pressure: Optional[float] = None  # psia
    temperature: Optional[float] = None  # °F
    is_source: Optional[bool] = False
    is_sink: Optional[bool] = False

class PipelineSegment(BaseModel):
    id: str
    start_point_id: str
    end_point_id: str
    length: float  # feet
    diameter: float = Field(..., gt=0)  # inches
    roughness: float = 0.0006  # inches
    inclination: Optional[float] = 0  # degrees
    flowrate: Optional[float] = None  # STB/d
    inlet_pressure: Optional[float] = None  # psia
    outlet_pressure: Optional[float] = None  # psia

class FluidProperties(BaseModel):
    type: str = "oil"  # oil, gas, water, multiphase
    oil_api: Optional[float] = None
    water_cut: Optional[float] = 0.0
    gor: Optional[float] = 0  # scf/STB
    gas_gravity: Optional[float] = None
    water_gravity: Optional[float] = 1.07
    temperature: float  # °F
    bubble_point: Optional[float] = None  # psia
    viscosity: Optional[float] = None  # cp

class PipelineHydraulicsInput(BaseModel):
    segment: PipelineSegment
    fluid: FluidProperties
    correlation: str = "beggs-brill"
    detailed_output: bool = False
    calculate_from: str = "inlet"  # inlet or outlet

class HydraulicsResult(BaseModel):
    segment_id: str
    inlet_pressure: float  # psia
    outlet_pressure: float  # psia
    pressure_drop: float  # psi
    flow_velocity: float  # ft/s
    reynolds_number: Optional[float] = None
    friction_factor: Optional[float] = None
    flow_regime: Optional[str] = None
    hold_up: Optional[float] = None
    elevation_pressure_drop: Optional[float] = None
    friction_pressure_drop: Optional[float] = None
    correlation: str
    pressure_points: Optional[List[float]] = None
    distance_points: Optional[List[float]] = None

class PipelineSystem(BaseModel):
    points: List[PipelinePoint]
    segments: List[PipelineSegment]
    fluid: FluidProperties

class SystemResult(BaseModel):
    system_id: str
    segment_results: List[HydraulicsResult]
    total_pressure_drop: float
    limiting_segments: List[str]
    choke_points: List[str]
    recommendations: Optional[List[str]] = None

class PipelineMaterial(BaseModel):
    id: str
    name: str
    roughness: float
    max_pressure: float

# Add the missing endpoint for material options
# In app/api/v1/routes/pipeline.py

@router.get("/pipeline/material-options", response_model=List[Dict[str, Any]])
async def get_material_options():
    """
    Get available pipeline material options with roughness values
    """
    logger.info("Received request for pipeline material options")
    
    materials = [
        {"id": 'carbon-steel', "name": 'Carbon Steel', "roughness": 0.0018, "max_pressure": 1500},
        {"id": 'stainless-steel', "name": 'Stainless Steel', "roughness": 0.0007, "max_pressure": 2500},
        {"id": 'hdpe', "name": 'HDPE', "roughness": 0.00006, "max_pressure": 200},
        {"id": 'pvc', "name": 'PVC', "roughness": 0.0002, "max_pressure": 150},
        {"id": 'coated-steel', "name": 'Epoxy Coated Steel', "roughness": 0.0003, "max_pressure": 2000},
        {"id": 'fiberglass', "name": 'Fiberglass', "roughness": 0.0001, "max_pressure": 300}
    ]
    
    logger.info(f"Returning {len(materials)} pipeline material options")
    return materials

@router.post("/pipeline/segment-hydraulics", response_model=Dict[str, Any])
async def calculate_segment_hydraulics(input_data: PipelineHydraulicsInput):
    """
    Calculate hydraulic performance for a single pipeline segment
    """
    try:
        logger.info(f"Received pipeline segment hydraulics calculation request using {input_data.correlation} method")
        
        # Convert pipeline input to hydraulics input format
        hydraulics_input = adapt_hydraulics_input_for_pipeline(input_data.dict())
        
        # Call your existing hydraulics calculation function
        hydraulics_result = calculate_hydraulics(hydraulics_input)
        
        # Convert result back to pipeline format
        result = adapt_hydraulics_output_for_pipeline(hydraulics_result, input_data.dict())
        
        logger.info(f"Pipeline calculation completed: pressure_drop={result['pressure_drop']:.2f} psi")
        return result
    
    except Exception as e:
        logger.error(f"Error in pipeline hydraulics calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add a simple direct calculation endpoint as fallback
@router.post("/pipeline/calculate-direct", response_model=HydraulicsResult)
async def calculate_direct(input_data: PipelineHydraulicsInput):
    """
    Simplified direct pressure drop calculation using Darcy-Weisbach
    when the full hydraulics API is not available
    """
    try:
        logger.info(f"Received direct pipeline calculation request")
        
        segment = input_data.segment
        fluid = input_data.fluid
        
        # Get basic parameters
        diameter = segment.diameter / 12  # Convert to feet
        length = segment.length  # In feet
        flowrate = segment.flowrate or 100  # Default 100 STB/d if not provided
        flow_ft3_sec = flowrate * 5.615 / 86400  # Convert STB/d to ft³/s
        
        # Calculate fluid density (lb/ft³)
        density = 62.4  # Water density
        if fluid.type == 'oil' and fluid.oil_api:
            # Convert API gravity to specific gravity
            specific_gravity = 141.5 / (fluid.oil_api + 131.5)
            density = specific_gravity * 62.4
        elif fluid.type == 'gas' and fluid.gas_gravity:
            # Simplified gas density calculation
            pressure = segment.inlet_pressure or 500  # psia
            temperature = fluid.temperature + 460  # °R
            z = 0.9  # Estimate compressibility factor
            mw = 28.97 * fluid.gas_gravity  # Molecular weight
            R = 10.73  # Gas constant (psia-ft³/lbmol-°R)
            density = (pressure * mw) / (z * R * temperature) * 144  # Convert to lb/ft³
        
        # Calculate area and velocity
        area = np.pi * (diameter / 2) ** 2  # ft²
        velocity = flow_ft3_sec / area if area > 0 else 0  # ft/s
        
        # Calculate viscosity and Reynolds number
        if fluid.type == 'oil' and fluid.oil_api:
            # Simplified oil viscosity estimation based on API
            viscosity = 1.0 / (fluid.oil_api ** 0.5) * 0.000672  # lb/ft-s
        elif fluid.type == 'water':
            viscosity = 0.000672  # ~1 cP at standard conditions
        else:
            viscosity = 0.000067  # For gas, ~0.01 cP
        
        reynolds = (density * velocity * diameter) / viscosity if viscosity > 0 else 100000
        
        # Calculate friction factor (simplified Colebrook approximation)
        roughness = segment.roughness / (12 * diameter)  # relative roughness
        
        if reynolds > 4000:  # Turbulent
            friction_factor = 0.25 / (np.log10(roughness / 3.7 + 5.74 / (reynolds ** 0.9))) ** 2
        elif reynolds > 2100:  # Transitional
            friction_factor = 0.032
        else:  # Laminar
            friction_factor = 64 / reynolds
        
        # Calculate friction drop
        friction_drop = friction_factor * (length / diameter) * (density / (2 * 32.2)) * (velocity ** 2) / 144  # psi
        
        # Calculate elevation drop
        inclination = segment.inclination or 0  # degrees
        elevation_change = length * np.sin(np.radians(inclination))  # ft
        elevation_drop = density * elevation_change / 144  # psi
        
        # Total pressure drop
        pressure_drop = friction_drop + elevation_drop
        
        # Inlet and outlet pressures
        inlet_pressure = segment.inlet_pressure or 500
        outlet_pressure = inlet_pressure - pressure_drop
        
        # Create result
        result = {
            "segment_id": segment.id,
            "inlet_pressure": float(inlet_pressure),
            "outlet_pressure": float(outlet_pressure),
            "pressure_drop": float(pressure_drop),
            "flow_velocity": float(velocity),
            "reynolds_number": float(reynolds),
            "friction_factor": float(friction_factor),
            "flow_regime": "calculated",
            "hold_up": None,
            "elevation_pressure_drop": float(elevation_drop),
            "friction_pressure_drop": float(friction_drop),
            "correlation": "darcy-weisbach",
            "pressure_points": None,
            "distance_points": None
        }
        
        logger.info(f"Direct calculation completed: pressure_drop={pressure_drop:.2f} psi")
        return result
    
    except Exception as e:
        logger.error(f"Error in direct pipeline calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))