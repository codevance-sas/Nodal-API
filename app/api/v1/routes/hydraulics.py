import logging
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Any, Optional

from app.schemas.hydraulics import (
    HydraulicsInput, HydraulicsResult,
    FlowRateInput, GeometryInput
)
from app.services.hydraulics import hydraulics_service

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["hydraulics"])


@router.post(
    "/calculate",
    response_model=HydraulicsResult,
    summary="Calculate well hydraulics",
)
async def calculate_hydraulics_endpoint(
    data: HydraulicsInput,
) -> HydraulicsResult:
    """
    Calculate pressure profile and hydraulics parameters using the selected correlation
    """
    try:
        return hydraulics_service.calculate_hydraulics(data)
    except Exception as e:
        logger.error(f"Error in hydraulics calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend")
async def recommend_method_endpoint(data: HydraulicsInput) -> Dict[str, str]:
    """
    Recommend the most suitable correlation method based on input data
    """
    try:
        method = hydraulics_service.recommend_method(data)
        return {"recommended_method": method}
    except Exception as e:
        logger.error(f"Error in method recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_methods_endpoint(
    data: HydraulicsInput,
    methods: Optional[List[str]] = Query(None, description="List of methods to compare")
) -> Dict[str, Any]:
    """
    Compare results from different hydraulics correlations
    """
    try:
        return hydraulics_service.compare_methods(data, methods)
    except Exception as e:
        logger.error(f"Error in method comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/methods")
async def get_available_methods():
    """
    Return the list of available correlation methods
    """
    return {
        "methods": hydraulics_service.get_available_methods()
    }


@router.post("/sensitivity/flowrate")
async def flow_rate_sensitivity_endpoint(data: FlowRateInput) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on flow rates
    """
    try:
        return hydraulics_service.flow_rate_sensitivity(data)
    except Exception as e:
        logger.error(f"Error in flow rate sensitivity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sensitivity/tubing")
async def tubing_sensitivity_endpoint(data: GeometryInput) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on tubing diameter
    """
    try:
        return hydraulics_service.tubing_sensitivity(data)
    except Exception as e:
        logger.error(f"Error in tubing sensitivity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/example-input")
async def get_example_input_endpoint():
    """
    Return an example input for the hydraulics calculation
    """
    return hydraulics_service.get_example_input()