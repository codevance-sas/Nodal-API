import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List

from app.schemas.pvt import PVTInput
from app.services.pvt import pvt_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["pvt"])

# Simple in-memory cache for route responses
curve_cache = {}

@router.post("/curves")
async def get_property_curves(data: PVTInput, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Calculate curves for all PVT properties.
    
    Args:
        data: PVTInput model with all input parameters
        background_tasks: FastAPI background tasks
        
    Returns:
        Dictionary with property curves
    """
    try:
        # Generate a cache key based on input parameters
        cache_key = f"curves_{data.api}_{data.gas_gravity}_{data.gor}_{data.temperature}"
        
        # Check if we have a cached result
        if cache_key in curve_cache:
            logger.info(f"Returning cached curves for {cache_key}")
            return curve_cache[cache_key]
        
        # Calculate curves
        logger.info(f"Calculating property curves for API: {data.api}, GOR: {data.gor}")
        result = pvt_service.calculate_property_curves(data)
        
        # Cache the result
        curve_cache[cache_key] = result
        
        # Add background task to clean up old cache entries if cache gets too large
        if len(curve_cache) > 100:
            background_tasks.add_task(lambda: curve_cache.clear())
        
        return result
    except ValueError as e:
        logger.error(f"Value error in curve calculation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating property curves: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommended-curves")
async def get_recommended_curves_endpoint(data: PVTInput) -> Dict[str, Any]:
    """
    Get recommended correlations for PVT properties.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with recommended correlations
    """
    try:
        return pvt_service.get_recommended_curves(data)
    except Exception as e:
        logger.error(f"Error getting recommended curves: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare/{property_name}")
async def compare_correlations_endpoint(property_name: str, data: PVTInput) -> Dict[str, Any]:
    """
    Compare different correlations for a specific property.
    
    Args:
        property_name: Name of the property to compare
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with comparison results
    """
    try:
        # Validate property name
        valid_properties = ["pb", "rs", "bo", "mu", "co", "z", "rho", "ift"]
        if property_name not in valid_properties:
            raise ValueError(f"Invalid property name. Must be one of: {', '.join(valid_properties)}")
        
        return pvt_service.compare_correlations(property_name, data)
    except ValueError as e:
        logger.error(f"Value error in correlation comparison: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error comparing correlations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bubble-points")
async def get_bubble_points_endpoint(data: PVTInput) -> Dict[str, Any]:
    """
    Calculate bubble point pressure using different correlations.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with bubble point values for each correlation
    """
    try:
        return pvt_service.calculate_bubble_points(data)
    except Exception as e:
        logger.error(f"Error calculating bubble points: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
async def clear_curve_cache() -> Dict[str, Any]:
    """
    Clear the curve cache to force fresh calculations.
    
    Returns:
        Status message
    """
    try:
        # Count cache entries before clearing
        cache_count = len(curve_cache)
        
        # Clear the cache
        curve_cache.clear()
        
        # Also clear calculation cache in the service
        calc_cache_count = pvt_service.clear_calculation_cache()
        
        return {
            "status": "success",
            "message": f"Cache cleared. {cache_count} route cache entries and {calc_cache_count} calculation cache entries removed."
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Error clearing cache")


@router.post("/calculate")
async def calculate_pvt_endpoint(data: PVTInput) -> Dict[str, Any]:
    """
    Calculate PVT properties at a single pressure point.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with calculated PVT properties
    """
    try:
        return pvt_service.calculate_pvt_at_bubble_point(data)
    except ValueError as e:
        logger.error(f"Value error in PVT calculation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in PVT calculation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")