# app/api/v1/routes/pvt.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List
import logging

from app.schemas.pvt import PVTInput
from app.services.pvt.curve_service import (
    calculate_property_curves,
    calculate_bubble_points,
    get_recommended_curves,
    compare_correlations,
    clear_calculation_cache
)

router = APIRouter(tags=["pvt"])
logger = logging.getLogger(__name__)

# Cache for previously calculated curves to improve performance
curve_cache = {}


@router.post("/curve")
async def get_property_curves(data: PVTInput, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    FastAPI endpoint to calculate property curves for all correlations.
    
    Args:
        data: PVTInput model with all input parameters
        background_tasks: FastAPI background task manager
        
    Returns:
        Dictionary with curve data for all properties
    """
    try:
        # Clear cache if a debug flag is set to force recalculation
        force_recalculate = getattr(data, "force_recalculate", False)
        
        # Create a cache key based on the input data
        # Exclude step_size from cache key since we use adaptive pressure range
        cache_key = f"{data.api}_{data.gas_gravity}_{data.gor}_{data.temperature}"
        cache_key += f"_{data.pb or 0}_{data.stock_temp}_{data.stock_pressure}"
        cache_key += f"_{data.co2_frac or 0}_{data.h2s_frac or 0}_{data.n2_frac or 0}"
        
        # Add correlations to cache key
        if data.correlations:
            for k, v in sorted(data.correlations.items()):
                cache_key += f"_{k}:{v}"
        
        # Check if we have this in cache
        if cache_key in curve_cache and not force_recalculate:
            logger.info(f"Returning cached curve data for {cache_key}")
            return curve_cache[cache_key]
        
        # Calculate curves using the service
        curves = calculate_property_curves(data)
        
        # Store in cache (in background to not block response)
        background_tasks.add_task(lambda: curve_cache.update({cache_key: curves}))
        
        return curves
        
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/curve/recommended")
async def get_recommended_curves_endpoint(data: PVTInput) -> Dict[str, Any]:
    """
    Get only the recommended correlation curves.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with curve data for only the recommended correlations
    """
    try:
        return get_recommended_curves(data)
    except Exception as e:
        logger.error(f"Error in recommended curves: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/curve/compare/{property_name}")
async def compare_correlations_endpoint(property_name: str, data: PVTInput) -> Dict[str, Any]:
    """
    Get comparison data for a specific property with all available correlations.
    
    Args:
        property_name: Name of the property to compare (rs, bo, etc.)
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with comparative curves and metadata
    """
    try:
        # Validate property name (handled in the service, but we need to check here for HTTP errors)
        valid_properties = ["rs", "bo", "mu", "co", "z", "bg", "rho", "ift", "pb"]
        if property_name not in valid_properties:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid property name. Must be one of: {', '.join(valid_properties)}"
            )
            
        return compare_correlations(property_name, data)
        
    except Exception as e:
        logger.error(f"Error in correlation comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/curve/bubble-points")
async def get_bubble_points_endpoint(data: PVTInput) -> Dict[str, Any]:
    """
    Calculate bubble point pressures for all correlations.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with bubble point values for each correlation
    """
    try:
        return calculate_bubble_points(data)
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
        calc_cache_count = clear_calculation_cache()
        
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
        logger.info(f"Received PVT calculation request for API: {data.api}, GOR: {data.gor}")
        
        # We can leverage the existing curve calculation code and extract a single point
        # First, calculate the curves
        curves = calculate_property_curves(data)
        
        # Extract recommended correlations from metadata
        recommended_correlations = curves.get("metadata", {}).get("recommended_correlations", {})
        
        # Get bubble point pressure
        bubble_points = curves.get("metadata", {}).get("bubble_points", {})
        recommended_pb_method = recommended_correlations.get("pb", "standing")
        bubble_point = bubble_points.get(recommended_pb_method, 0)
        
        # Find the pressure point closest to the bubble point
        pressures = curves.get("pressure", [])
        if not pressures:
            raise ValueError("No pressure points found in calculation results")
        
        # Default to using the bubble point pressure or the middle pressure point
        target_pressure = bubble_point or pressures[len(pressures) // 2]
        
        # Find index of closest pressure to target
        closest_idx = min(range(len(pressures)), key=lambda i: abs(pressures[i] - target_pressure))
        
        # Extract property values at the selected pressure
        result = {
            "api": data.api,
            "gas_gravity": data.gas_gravity,
            "gor": data.gor,
            "temperature": data.temperature,
            "water_gravity": data.water_gravity if hasattr(data, "water_gravity") else 1.0,
            "stock_temp": data.stock_temp,
            "stock_pressure": data.stock_pressure,
            "co2_frac": data.co2_frac,
            "h2s_frac": data.h2s_frac,
            "n2_frac": data.n2_frac,
            "pressure": pressures[closest_idx],
            "correlations": recommended_correlations,
            "results": []
        }
        
        # Get the values for each property using the recommended correlation
        pvt_point = {}
        
        for prop in ["rs", "bo", "mu", "co", "z", "bg", "rho", "ift"]:
            if prop in curves and recommended_correlations.get(prop) in curves[prop]:
                method = recommended_correlations.get(prop)
                values = curves[prop][method]
                if values and len(values) > closest_idx:
                    pvt_point[prop] = values[closest_idx]
        
        # Add bubble point
        pvt_point["pb"] = bubble_point
        
        # Add pressure
        pvt_point["pressure"] = pressures[closest_idx]
        
        # Add the property values to the result
        result["results"] = [pvt_point]
        
        logger.info(f"PVT calculation completed successfully")
        return result
        
    except ValueError as e:
        logger.error(f"Value error in PVT calculation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in PVT calculation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")