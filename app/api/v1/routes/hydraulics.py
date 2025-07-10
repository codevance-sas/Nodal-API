# app/api/v1/routes/hydraulics.py
import numpy as np
import copy
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError
from typing import List, Dict, Any, Optional
import logging

from app.schemas.hydraulics import (
    HydraulicsInput, HydraulicsResult,
    FlowRateInput, GeometryInput
)
from app.services.hydraulics.engine import (
    calculate_hydraulics,
    compare_methods,
    recommend_method,
    flow_rate_sensitivity,
    tubing_sensitivity,
    get_example_input
)
from app.services.hydraulics.funcs import available_methods

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
        logger.info(f"Received hydraulics calculation request {data.method}")
        result = calculate_hydraulics(data)
        logger.info(f"Calculation completed: BHP={result.bottomhole_pressure:.2f} psia")
        return result
    except Exception as e:
        logger.error(f"Error in hydraulics calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend")
async def recommend_method_endpoint(data: HydraulicsInput) -> Dict[str, str]:
    """
    Recommend the most suitable correlation method based on input data
    """
    try:
        method = recommend_method(data)
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
        logger.info(f"Received request to compare hydraulics methods")
        results = compare_methods(data, methods)
        return results
    except Exception as e:
        logger.error(f"Error in method comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/methods")
async def get_available_methods():
    """
    Return the list of available correlation methods
    """
    return {
        "methods": available_methods()
    }


@router.post("/sensitivity/flowrate")
async def flow_rate_sensitivity_endpoint(data: FlowRateInput) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on flow rates
    """
    try:
        result = flow_rate_sensitivity(
            data.base_data,
            data.min_oil_rate,
            data.max_oil_rate,
            data.steps,
            data.water_cut,
            data.gor
        )
        return result
    except Exception as e:
        logger.error(f"Error in flow rate sensitivity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sensitivity/tubing")
async def tubing_sensitivity_endpoint(data: GeometryInput) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on tubing diameter
    """
    try:
        result = tubing_sensitivity(
            data.base_data,
            data.min_tubing_id,
            data.max_tubing_id,
            data.steps
        )
        return result
    except Exception as e:
        logger.error(f"Error in tubing sensitivity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/example-input")
async def get_example_input_endpoint():
    """
    Return an example input for the hydraulics calculation
    """
    return get_example_input()