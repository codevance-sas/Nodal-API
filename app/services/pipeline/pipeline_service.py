import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from app.services.hydraulics import hydraulics_service
from app.services.hydraulics.extensions.pipeline import (
    calculate_elevation_effect,
    calculate_fitting_losses,
    adapt_hydraulics_input_for_pipeline,
    adapt_hydraulics_output_for_pipeline
)

# Configure logging
logger = logging.getLogger(__name__)

class PipelineService:
    """
    Service for handling pipeline calculations.
    This service encapsulates all pipeline-related logic to improve separation of concerns.
    """
    
    def get_material_options(self) -> List[Dict[str, Any]]:
        """
        Get available pipeline material options.
        
        Returns:
            List of pipeline material options
        """
        logger.info("Getting pipeline material options")
        
        materials = [
            {"id": 'carbon-steel', "name": 'Carbon Steel', "roughness": 0.0018, "max_pressure": 1500},
            {"id": 'stainless-steel', "name": 'Stainless Steel', "roughness": 0.0007, "max_pressure": 2500},
            {"id": 'hdpe', "name": 'HDPE', "roughness": 0.00006, "max_pressure": 200},
            {"id": 'pvc', "name": 'PVC', "roughness": 0.0002, "max_pressure": 150},
            {"id": 'coated-steel', "name": 'Epoxy Coated Steel', "roughness": 0.0003, "max_pressure": 2000},
            {"id": 'fiberglass', "name": 'Fiberglass', "roughness": 0.0001, "max_pressure": 300}
        ]
        
        logger.info(f"Returning {len(materials)} pipeline material options")
        return materials
    
    def calculate_segment_hydraulics(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate hydraulic performance for a single pipeline segment.
        
        Args:
            input_data: Pipeline input data
            
        Returns:
            Dictionary with calculation results
            
        Raises:
            Exception: If calculation fails
        """
        try:
            logger.info(f"Calculating pipeline segment hydraulics using {input_data.get('correlation', 'default')} method")
            
            # Convert pipeline input to hydraulics input format
            hydraulics_input = adapt_hydraulics_input_for_pipeline(input_data)
            
            # Call hydraulics calculation function
            hydraulics_result = hydraulics_service.calculate_hydraulics(hydraulics_input)
            
            # Convert result back to pipeline format
            result = adapt_hydraulics_output_for_pipeline(hydraulics_result, input_data)
            
            logger.info(f"Pipeline calculation completed: pressure_drop={result['pressure_drop']:.2f} psi")
            return result
        
        except Exception as e:
            logger.error(f"Error in pipeline hydraulics calculation: {str(e)}")
            raise
    
    def calculate_direct(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simplified direct pressure drop calculation using Darcy-Weisbach
        when the full hydraulics API is not available.
        
        Args:
            input_data: Pipeline input data
            
        Returns:
            Dictionary with calculation results
            
        Raises:
            Exception: If calculation fails
        """
        try:
            logger.info("Performing direct pipeline calculation")
            
            segment = input_data.get("segment", {})
            fluid = input_data.get("fluid", {})
            
            # Get basic parameters
            diameter = segment.get("diameter", 0) / 12  # Convert to feet
            length = segment.get("length", 0)  # In feet
            flowrate = segment.get("flowrate", 100)  # Default 100 STB/d if not provided
            flow_ft3_sec = flowrate * 5.615 / 86400  # Convert STB/d to ft³/s
            
            # Calculate fluid density (lb/ft³)
            density = 62.4  # Water density
            if fluid.get("type") == 'oil' and fluid.get("oil_api"):
                # Convert API gravity to specific gravity
                specific_gravity = 141.5 / (fluid.get("oil_api") + 131.5)
                density = specific_gravity * 62.4
            elif fluid.get("type") == 'gas' and fluid.get("gas_gravity"):
                # Simplified gas density calculation
                pressure = segment.get("inlet_pressure", 500)  # psia
                temperature = fluid.get("temperature", 60) + 460  # °R
                z = 0.9  # Estimate compressibility factor
                mw = 28.97 * fluid.get("gas_gravity")  # Molecular weight
                R = 10.73  # Gas constant (psia-ft³/lbmol-°R)
                density = (pressure * mw) / (z * R * temperature) * 144  # Convert to lb/ft³
            
            # Calculate area and velocity
            area = np.pi * (diameter / 2) ** 2  # ft²
            velocity = flow_ft3_sec / area if area > 0 else 0  # ft/s
            
            # Calculate viscosity and Reynolds number
            if fluid.get("type") == 'oil' and fluid.get("oil_api"):
                # Simplified oil viscosity estimation based on API
                viscosity = 1.0 / (fluid.get("oil_api") ** 0.5) * 0.000672  # lb/ft-s
            elif fluid.get("type") == 'water':
                viscosity = 0.000672  # ~1 cP at standard conditions
            else:
                viscosity = 0.000067  # For gas, ~0.01 cP
            
            reynolds = (density * velocity * diameter) / viscosity if viscosity > 0 else 100000
            
            # Calculate friction factor (simplified Colebrook approximation)
            roughness = segment.get("roughness", 0.0018) / (12 * diameter)  # relative roughness
            
            if reynolds > 4000:  # Turbulent
                friction_factor = 0.25 / (np.log10(roughness / 3.7 + 5.74 / (reynolds ** 0.9))) ** 2
            elif reynolds > 2100:  # Transitional
                friction_factor = 0.032
            else:  # Laminar
                friction_factor = 64 / reynolds
            
            # Calculate friction drop
            friction_drop = friction_factor * (length / diameter) * (density / (2 * 32.2)) * (velocity ** 2) / 144  # psi
            
            # Calculate elevation drop
            inclination = segment.get("inclination", 0)  # degrees
            elevation_change = length * np.sin(np.radians(inclination))  # ft
            elevation_drop = density * elevation_change / 144  # psi
            
            # Total pressure drop
            pressure_drop = friction_drop + elevation_drop
            
            # Inlet and outlet pressures
            inlet_pressure = segment.get("inlet_pressure", 500)
            outlet_pressure = inlet_pressure - pressure_drop
            
            # Create result
            result = {
                "segment_id": segment.get("id", "unknown"),
                "inlet_pressure": float(inlet_pressure),
                "outlet_pressure": float(outlet_pressure),
                "pressure_drop": float(pressure_drop),
                "flow_velocity": float(velocity),
                "reynolds_number": float(reynolds),
                "friction_factor": float(friction_factor),
                "flow_regime": "calculated",
                "hold_up": None,
                "elevation_pressure_drop": float(elevation_drop),
                "friction_pressure_drop": float(friction_drop),
                "acceleration_pressure_drop": 0.0,
                "fitting_pressure_drop": 0.0
            }
            
            logger.info(f"Direct pipeline calculation completed: pressure_drop={pressure_drop:.2f} psi")
            return result
            
        except Exception as e:
            logger.error(f"Error in direct pipeline calculation: {str(e)}")
            raise
    
    def calculate_elevation_effect(self, length: float, inclination: float, fluid_density: float) -> float:
        """
        Calculate the pressure effect due to elevation change.
        
        Args:
            length: Pipeline length in feet
            inclination: Pipeline inclination in degrees
            fluid_density: Fluid density in lb/ft³
            
        Returns:
            Pressure effect in psi
        """
        return calculate_elevation_effect(length, inclination, fluid_density)
    
    def calculate_fitting_losses(self, fittings: Dict[str, int], diameter: float, flowrate: float) -> float:
        """
        Calculate pressure losses due to fittings.
        
        Args:
            fittings: Dictionary of fitting types and counts
            diameter: Pipeline diameter in inches
            flowrate: Flow rate in STB/d
            
        Returns:
            Pressure loss in psi
        """
        return calculate_fitting_losses(fittings, diameter, flowrate)

# Create a singleton instance
pipeline_service = PipelineService()