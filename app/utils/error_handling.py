# app/utils/error_handling.py

import logging
import traceback
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CalculationError(Exception):
    """Base class for calculation errors"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class PipelineCalculationError(CalculationError):
    """Specific error for pipeline calculations"""
    pass

class HydraulicsCalculationError(CalculationError):
    """Specific error for hydraulics calculations"""
    pass

class PVTCalculationError(CalculationError):
    """Specific error for PVT calculations"""
    pass

def handle_calculation_error(func):
    """
    Decorator for handling calculation errors with proper logging
    
    Args:
        func: Function to decorate
        
    Returns:
        Wrapped function with error handling
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CalculationError as e:
            # Already formatted error, just log and re-raise
            logger.error(f"{type(e).__name__}: {e.message}")
            raise
        except Exception as e:
            # Format generic error for better traceability
            tb = traceback.format_exc()
            logger.error(f"Error in {func.__name__}: {str(e)}\n{tb}")
            
            # Create appropriate error type based on function name/module
            module_name = func.__module__.split('.')[-1] if hasattr(func, '__module__') else ""
            if 'pipeline' in module_name or 'pipeline' in func.__name__:
                raise PipelineCalculationError(str(e), {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs),
                })
            elif 'hydraulics' in module_name or 'hydraulics' in func.__name__:
                raise HydraulicsCalculationError(str(e), {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs),
                })
            elif 'pvt' in module_name or 'pvt' in func.__name__:
                raise PVTCalculationError(str(e), {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs),
                })
            else:
                raise CalculationError(str(e), {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs),
                })
    
    return wrapper