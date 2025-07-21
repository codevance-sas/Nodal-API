import logging
from typing import Dict, Any, List, Optional

from app.schemas.pvt import PVTInput, PVTResult
from app.services.pvt.engine import (
    validate_input,
    generate_pressure_range,
    calculate_pvt,
    get_pvt_at_pressure,
    bulk_calculate_pvt
)
from app.services.pvt.curve_service import (
    calculate_property_curves,
    calculate_bubble_points,
    get_recommended_curves,
    compare_correlations,
    clear_calculation_cache
)

# Configure logging
logger = logging.getLogger(__name__)

class PVTService:
    """
    Service for handling PVT calculations and property curves.
    This service encapsulates all PVT-related logic to improve separation of concerns.
    """
    
    def validate_input(self, data: PVTInput) -> Dict[str, Any]:
        """
        Validate PVT input data.
        
        Args:
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with validation messages
        """
        logger.info(f"Validating PVT input for API: {data.api}, GOR: {data.gor}")
        return validate_input(data)
    
    def calculate_pvt(self, data: PVTInput) -> Dict[str, Any]:
        """
        Calculate PVT properties for a range of pressures.
        
        Args:
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with calculation results
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Calculating PVT properties for API: {data.api}, GOR: {data.gor}")
        return calculate_pvt(data)
    
    def get_pvt_at_pressure(self, data: PVTInput, target_pressure: float) -> Optional[PVTResult]:
        """
        Calculate PVT properties at a specific pressure.
        
        Args:
            data: Input data for PVT calculation
            target_pressure: Pressure at which to calculate properties
            
        Returns:
            PVT properties at the specified pressure, or None if calculation fails
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Calculating PVT at pressure {target_pressure} psia")
        return get_pvt_at_pressure(data, target_pressure)
    
    def bulk_calculate_pvt(self, data: PVTInput, pressures: List[float]) -> Dict[str, Any]:
        """
        Calculate PVT properties for a list of pressures.
        
        Args:
            data: Input data for PVT calculation
            pressures: List of pressures at which to calculate properties
            
        Returns:
            Dictionary with calculation results
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Bulk calculating PVT for {len(pressures)} pressure points")
        return bulk_calculate_pvt(data, pressures)
    
    def calculate_property_curves(self, data: PVTInput) -> Dict[str, Any]:
        """
        Calculate curves for all PVT properties.
        
        Args:
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with property curves
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Calculating property curves for API: {data.api}, GOR: {data.gor}")
        return calculate_property_curves(data)
    
    def calculate_bubble_points(self, data: PVTInput) -> Dict[str, Any]:
        """
        Calculate bubble point pressure using different correlations.
        
        Args:
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with bubble point values for each correlation
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Calculating bubble points for API: {data.api}, GOR: {data.gor}")
        return calculate_bubble_points(data)
    
    def get_recommended_curves(self, data: PVTInput) -> Dict[str, Any]:
        """
        Get recommended correlations for PVT properties.
        
        Args:
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with recommended correlations
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Getting recommended curves for API: {data.api}, GOR: {data.gor}")
        return get_recommended_curves(data)
    
    def compare_correlations(self, property_name: str, data: PVTInput) -> Dict[str, Any]:
        """
        Compare different correlations for a specific property.
        
        Args:
            property_name: Name of the property to compare
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with comparison results
            
        Raises:
            Exception: If calculation fails
        """
        logger.info(f"Comparing correlations for {property_name}")
        return compare_correlations(property_name, data)
    
    def clear_calculation_cache(self) -> int:
        """
        Clear the calculation cache.
        
        Returns:
            Number of cache entries cleared
        """
        logger.info("Clearing PVT calculation cache")
        return clear_calculation_cache()
    
    def calculate_pvt_at_bubble_point(self, data: PVTInput) -> Dict[str, Any]:
        """
        Calculate PVT properties at the bubble point pressure.
        
        Args:
            data: Input data for PVT calculation
            
        Returns:
            Dictionary with PVT properties at the bubble point
            
        Raises:
            Exception: If calculation fails
        """
        try:
            logger.info(f"Calculating PVT at bubble point for API: {data.api}, GOR: {data.gor}")
            
            # Calculate property curves
            curves = self.calculate_property_curves(data)
            
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
            
            # Find index of closest pressure to bubble point
            closest_idx = min(range(len(pressures)), key=lambda i: abs(pressures[i] - bubble_point))
            
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
            
            logger.info(f"PVT calculation at bubble point completed successfully")
            return result
            
        except ValueError as e:
            logger.error(f"Value error in PVT calculation at bubble point: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in PVT calculation at bubble point: {str(e)}")
            raise

# Create a singleton instance
pvt_service = PVTService()