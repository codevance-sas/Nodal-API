# app/services/hydraulics/extensions/pipeline_cache.py

import time
import json
import hashlib
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Simple in-memory cache implementation
_pipeline_calculations_cache = {}

def cache_pipeline_result(cache_key: str, result: Dict[str, Any], ttl_seconds: int = 3600) -> None:
    """
    Cache a pipeline calculation result
    
    Args:
        cache_key: Unique identifier for this calculation
        result: Calculation result to cache
        ttl_seconds: Time-to-live in seconds (default 1 hour)
    """
    _pipeline_calculations_cache[cache_key] = {
        "result": result,
        "expires_at": time.time() + ttl_seconds
    }
    logger.debug(f"Cached pipeline result with key: {cache_key}, expires in {ttl_seconds}s")

def get_cached_pipeline_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a cached pipeline calculation result if available
    
    Args:
        cache_key: Unique identifier for the calculation
        
    Returns:
        Cached result or None if not found or expired
    """
    cache_entry = _pipeline_calculations_cache.get(cache_key)
    
    if not cache_entry:
        return None
    
    # Check if expired
    if cache_entry["expires_at"] < time.time():
        # Remove expired entry
        _pipeline_calculations_cache.pop(cache_key)
        return None
    
    logger.debug(f"Retrieved cached pipeline result for key: {cache_key}")
    return cache_entry["result"]

def clear_pipeline_cache() -> int:
    """
    Clear all cached pipeline calculations
    
    Returns:
        Number of entries removed
    """
    count = len(_pipeline_calculations_cache)
    _pipeline_calculations_cache.clear()
    logger.info(f"Cleared pipeline cache, removed {count} entries")
    return count

def generate_pipeline_cache_key(input_data: Dict[str, Any]) -> str:
    """
    Generate a unique cache key based on input parameters
    
    Args:
        input_data: Pipeline input data
        
    Returns:
        String key for caching
    """
    # Extract key parameters that affect the calculation
    segment = input_data.get("segment", {})
    fluid = input_data.get("fluid", {})
    correlation = input_data.get("correlation", "beggs-brill")
    
    # Create a string representation of key parameters
    key_data = {
        "diameter": segment.get("diameter", 0),
        "length": segment.get("length", 0),
        "flowrate": segment.get("flowrate", 0),
        "inlet_pressure": segment.get("inlet_pressure", 0),
        "fluid_type": fluid.get("type", "oil"),
        "oil_api": fluid.get("oil_api", 0),
        "water_cut": fluid.get("water_cut", 0),
        "gor": fluid.get("gor", 0),
        "gas_gravity": fluid.get("gas_gravity", 0),
        "temperature": fluid.get("temperature", 0),
        "correlation": correlation
    }
    
    # Convert to JSON string and hash for a shorter key
    json_str = json.dumps(key_data, sort_keys=True)
    hash_obj = hashlib.md5(json_str.encode())
    return hash_obj.hexdigest()