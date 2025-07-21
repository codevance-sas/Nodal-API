import logging
from typing import Dict, Any, List, Optional

from app.schemas.hydraulics import (
    HydraulicsInput, HydraulicsResult, 
    FlowRateInput, GeometryInput
)
from app.services.hydraulics.engine import (
    calculate_hydraulics as engine_calculate_hydraulics,
    compare_methods as engine_compare_methods,
    recommend_method as engine_recommend_method,
    flow_rate_sensitivity as engine_flow_rate_sensitivity,
    tubing_sensitivity as engine_tubing_sensitivity,
    get_example_input as engine_get_example_input
)
from app.services.hydraulics.funcs import available_methods as engine_available_methods

# Configure logging
logger = logging.getLogger(__name__)

class HydraulicsService:
    """
    Service for handling hydraulics calculations.
    This service encapsulates all hydraulics-related logic to improve separation of concerns.
    """
    
    def calculate_hydraulics(self, data: HydraulicsInput) -> HydraulicsResult:
        """
        Calculate pressure profile and hydraulics parameters using the selected correlation.
        
        Args:
            data: Input data for hydraulics calculation
            
        Returns:
            Hydraulics calculation result
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Performing hydraulics calculation using {data.method}")
        result = engine_calculate_hydraulics(data)
        logger.info(f"Calculation completed: BHP={result.bottomhole_pressure:.2f} psia")
        return result
    
    def recommend_method(self, data: HydraulicsInput) -> str:
        """
        Recommend the most suitable correlation method based on input data.
        
        Args:
            data: Input data for hydraulics calculation
            
        Returns:
            Recommended method name
            
        Raises:
            Exception: If recommendation fails
        """
        logger.info("Recommending hydraulics correlation method")
        method = engine_recommend_method(data)
        logger.info(f"Recommended method: {method}")
        return method
    
    def compare_methods(self, data: HydraulicsInput, methods: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compare results from different hydraulics correlations.
        
        Args:
            data: Input data for hydraulics calculation
            methods: List of methods to compare, or None for all methods
            
        Returns:
            Dictionary with comparison results
            
        Raises:
            Exception: If comparison fails
        """
        logger.info("Comparing hydraulics correlation methods")
        results = engine_compare_methods(data, methods)
        return results
    
    def get_available_methods(self) -> List[str]:
        """
        Get list of available correlation methods.
        
        Returns:
            List of method names
        """
        return engine_available_methods()
    
    def flow_rate_sensitivity(self, data: FlowRateInput) -> Dict[str, Any]:
        """
        Perform sensitivity analysis on flow rates.
        
        Args:
            data: Input data for sensitivity analysis
            
        Returns:
            Dictionary with sensitivity analysis results
            
        Raises:
            Exception: If analysis fails
        """
        logger.info(f"Performing flow rate sensitivity analysis from {data.min_oil_rate} to {data.max_oil_rate} STB/d")
        result = engine_flow_rate_sensitivity(
            data.base_data,
            data.min_oil_rate,
            data.max_oil_rate,
            data.steps,
            data.water_cut,
            data.gor
        )
        return result
    
    def tubing_sensitivity(self, data: GeometryInput) -> Dict[str, Any]:
        """
        Perform sensitivity analysis on tubing diameter.
        
        Args:
            data: Input data for sensitivity analysis
            
        Returns:
            Dictionary with sensitivity analysis results
            
        Raises:
            Exception: If analysis fails
        """
        logger.info(f"Performing tubing sensitivity analysis from {data.min_tubing_id} to {data.max_tubing_id} inches")
        result = engine_tubing_sensitivity(
            data.base_data,
            data.min_tubing_id,
            data.max_tubing_id,
            data.steps
        )
        return result
    
    def get_example_input(self) -> HydraulicsInput:
        """
        Get example input for hydraulics calculation.
        
        Returns:
            Example input data
        """
        return engine_get_example_input()

# Create a singleton instance
hydraulics_service = HydraulicsService()