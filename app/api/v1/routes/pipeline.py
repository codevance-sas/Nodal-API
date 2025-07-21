import numpy as np
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel, Field

from app.services.pipeline import pipeline_service

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["pipeline"])

# Simple models directly in this file - in the future, move these to schemas directory
class PipelinePoint(BaseModel):
    """A point in a pipeline system"""
    id: str
    name: Optional[str] = None
    x: float = 0
    y: float = 0
    elevation: float = 0
    pressure: Optional[float] = None
    temperature: Optional[float] = None

class PipelineSegment(BaseModel):
    """A segment in a pipeline system"""
    id: str
    name: Optional[str] = None
    start_point: str
    end_point: str
    length: float
    diameter: float
    roughness: float = 0.0018
    inclination: float = 0
    inlet_pressure: Optional[float] = None
    flowrate: Optional[float] = None

class FluidProperties(BaseModel):
    """Fluid properties for pipeline calculations"""
    type: str = "water"  # water, oil, gas
    temperature: float = 60
    oil_api: Optional[float] = None
    water_gravity: Optional[float] = None
    gas_gravity: Optional[float] = None
    viscosity: Optional[float] = None

class PipelineHydraulicsInput(BaseModel):
    """Input for pipeline hydraulics calculation"""
    segment: PipelineSegment
    fluid: FluidProperties
    correlation: str = "beggs-brill"

class HydraulicsResult(BaseModel):
    """Result of hydraulics calculation"""
    segment_id: str
    inlet_pressure: float
    outlet_pressure: float
    pressure_drop: float
    flow_velocity: float
    reynolds_number: float
    friction_factor: float
    flow_regime: str
    hold_up: Optional[float] = None
    elevation_pressure_drop: float
    friction_pressure_drop: float
    acceleration_pressure_drop: float
    fitting_pressure_drop: float

class PipelineSystem(BaseModel):
    """A complete pipeline system"""
    points: List[PipelinePoint]
    segments: List[PipelineSegment]

class SystemResult(BaseModel):
    """Result of system calculation"""
    points: List[PipelinePoint]
    segments: List[HydraulicsResult]
    total_pressure_drop: float
    total_length: float

class PipelineMaterial(BaseModel):
    """Pipeline material properties"""
    id: str
    name: str
    roughness: float
    max_pressure: float

@router.get("/pipeline/materials", response_model=List[PipelineMaterial])
async def get_material_options():
    """
    Get available pipeline material options
    """
    try:
        return pipeline_service.get_material_options()
    except Exception as e:
        logger.error(f"Error getting pipeline materials: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pipeline/segment-hydraulics", response_model=Dict[str, Any])
async def calculate_segment_hydraulics(input_data: PipelineHydraulicsInput):
    """
    Calculate hydraulic performance for a single pipeline segment
    """
    try:
        logger.info(f"Received pipeline segment hydraulics calculation request using {input_data.correlation} method")
        result = pipeline_service.calculate_segment_hydraulics(input_data.dict())
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
        result = pipeline_service.calculate_direct(input_data.dict())
        logger.info(f"Direct pipeline calculation completed: pressure_drop={result['pressure_drop']:.2f} psi")
        return result
    except Exception as e:
        logger.error(f"Error in direct pipeline calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))