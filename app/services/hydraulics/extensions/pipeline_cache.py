# app/services/hydraulics/extensions/pipeline_cache.py

import time
import json
import hashlib
import functools
from typing import Dict, Any, Optional, Callable, Tuple, List, Union
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_MAX_SIZE = 1000  # Maximum number of items in cache
CACHE_TTL_SECONDS = 3600  # Default time-to-live in seconds (1 hour)
CACHE_STATS = {
    "hits": 0,
    "misses": 0,
    "size": 0,
    "evictions": 0,
    "expirations": 0
}

# Simple in-memory cache implementation
_pipeline_calculations_cache: Dict[str, Dict[str, Any]] = {}

def cache_pipeline_result(cache_key: str, result: Dict[str, Any], ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
    """
    Cache a pipeline calculation result
    
    Args:
        cache_key: Unique identifier for this calculation
        result: Calculation result to cache
        ttl_seconds: Time-to-live in seconds (default 1 hour)
    """
    # Check if we need to evict entries due to cache size limit
    if len(_pipeline_calculations_cache) >= CACHE_MAX_SIZE:
        _evict_cache_entries()
    
    _pipeline_calculations_cache[cache_key] = {
        "result": result,
        "expires_at": time.time() + ttl_seconds,
        "created_at": time.time()
    }
    CACHE_STATS["size"] = len(_pipeline_calculations_cache)
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
        CACHE_STATS["misses"] += 1
        return None
    
    # Check if expired
    if cache_entry["expires_at"] < time.time():
        # Remove expired entry
        _pipeline_calculations_cache.pop(cache_key)
        CACHE_STATS["expirations"] += 1
        CACHE_STATS["size"] = len(_pipeline_calculations_cache)
        CACHE_STATS["misses"] += 1
        return None
    
    CACHE_STATS["hits"] += 1
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
    CACHE_STATS["size"] = 0
    CACHE_STATS["evictions"] += count
    logger.info(f"Cleared pipeline cache, removed {count} entries")
    return count

def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the cache usage
    
    Returns:
        Dictionary with cache statistics
    """
    stats = CACHE_STATS.copy()
    stats["hit_ratio"] = stats["hits"] / (stats["hits"] + stats["misses"]) if (stats["hits"] + stats["misses"]) > 0 else 0
    return stats

def _evict_cache_entries(count: int = None) -> None:
    """
    Evict entries from the cache based on age
    
    Args:
        count: Number of entries to evict, defaults to 10% of max size
    """
    if not _pipeline_calculations_cache:
        return
    
    # Default to evicting 10% of the max cache size
    if count is None:
        count = max(1, CACHE_MAX_SIZE // 10)
    
    # Sort entries by creation time (oldest first)
    sorted_entries = sorted(
        _pipeline_calculations_cache.items(),
        key=lambda x: x[1]["created_at"]
    )
    
    # Evict the oldest entries
    for i in range(min(count, len(sorted_entries))):
        key = sorted_entries[i][0]
        _pipeline_calculations_cache.pop(key)
        CACHE_STATS["evictions"] += 1
    
    CACHE_STATS["size"] = len(_pipeline_calculations_cache)
    logger.info(f"Evicted {count} entries from pipeline cache")

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

def cached_calculation(ttl_seconds: int = CACHE_TTL_SECONDS):
    """
    Decorator for caching calculation results
    
    Args:
        ttl_seconds: Time-to-live in seconds
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Skip caching if explicitly disabled
            if kwargs.get("skip_cache", False):
                if "skip_cache" in kwargs:
                    kwargs.pop("skip_cache")
                return func(*args, **kwargs)
            
            # Generate a cache key from the function name and arguments
            func_name = func.__name__
            arg_str = json.dumps([str(arg) for arg in args], sort_keys=True)
            kwarg_str = json.dumps({k: str(v) for k, v in kwargs.items()}, sort_keys=True)
            key_str = f"{func_name}:{arg_str}:{kwarg_str}"
            cache_key = hashlib.md5(key_str.encode()).hexdigest()
            
            # Check cache
            cached_result = get_cached_pipeline_result(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Calculate result
            result = func(*args, **kwargs)
            
            # Cache result
            cache_pipeline_result(cache_key, result, ttl_seconds)
            
            return result
        return wrapper
    return decorator

# LRU cache for smaller, frequently used calculations
def memoize(maxsize: int = 128):
    """
    Decorator for memoizing function results using Python's lru_cache
    
    Args:
        maxsize: Maximum cache size
        
    Returns:
        Decorated function with memoization
    """
    def decorator(func: Callable):
        @lru_cache(maxsize=maxsize)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator