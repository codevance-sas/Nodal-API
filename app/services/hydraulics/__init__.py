# app/services/hydraulics/__init__.py

"""
Hydraulics module for NodalX - provides multiphase flow calculations and 
gas pipeline design capabilities for oil and gas systems.

This module includes:
- Multiphase flow correlations for wellbores
- Gas flow correlations for pipelines
- Fluid property calculations
- Specialized extensions for gas infrastructure design
"""

# Import the main engine functions to make them available at the module level
try:
    from .engine import (
        calculate_hydraulics,
        calculate_from_target_bhp,
        compare_methods,
        recommend_method,
        flow_rate_sensitivity,
        tubing_sensitivity,
        get_example_input,
        # Gas-specific functions
        calculate_gas_pipeline,
        calculate_gas_pipeline_diameter,
        gas_pipeline_sensitivity,
        calculate_compressor_station,
        design_gas_lift_system,
        design_gas_gathering_system
    )
except ImportError as e:
    # Log that some functions may not be available yet
    import logging
    logging.warning(f"Some hydraulics functions are not available: {str(e)}")

# Import utility functions
from .utils import calculate_fluid_properties

# Provide version information
__version__ = "2.0.0"  # Updated with gas infrastructure capabilities
__author__ = "NodalX Team"