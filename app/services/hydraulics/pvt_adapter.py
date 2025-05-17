# app/services/hydraulics/pvt_adapter.py
from typing import Dict, Any

# Import PVT module functions
from app.services.pvt.engine import get_pvt_at_pressure
from app.schemas.pvt import PVTInput
from app.services.pvt.water_props import calculate_water_fvf, calculate_water_viscosity


def convert_to_pvt_input(fluid_props: Dict[str, Any]) -> PVTInput:
    """
    Convert hydraulics fluid properties to PVT input model
    """
    return PVTInput(
        api=fluid_props["oil_gravity"],
        gas_gravity=fluid_props["gas_gravity"],
        gor=fluid_props.get("gor", 0),
        temperature=fluid_props.get("temperature", 75),
        pb=fluid_props.get("bubble_point", None),
        stock_temp=fluid_props.get("surface_temperature", 60),
        stock_pressure=fluid_props.get("stock_pressure", 14.7),
        water_gravity=fluid_props.get("water_gravity", 1.05),
        co2_frac=fluid_props.get("co2_frac", 0),
        h2s_frac=fluid_props.get("h2s_frac", 0),
        n2_frac=fluid_props.get("n2_frac", 0),
        correlations=fluid_props.get("correlations", None)
    )


def get_pvt_properties(
    pressure: float,
    temperature: float,
    fluid_props: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate PVT properties using the PVT module
    
    Args:
        pressure: Pressure at which to calculate properties (psia)
        temperature: Temperature at which to calculate properties (°F)
        fluid_props: Dictionary containing fluid properties
        
    Returns:
        Dictionary of PVT properties
    """
    # Update properties with current P/T
    props_dict = fluid_props.copy()
    props_dict["temperature"] = temperature
    
    # Convert to PVTInput object
    pvt_input = convert_to_pvt_input(props_dict)
    
    # Calculate PVT properties at the given pressure
    pvt_result = get_pvt_at_pressure(pvt_input, pressure)
    
    # If PVT result is None, use default values
    if pvt_result is None:
        return {
            "oil_fvf": 1.1,
            "oil_viscosity": 1.0,
            "water_fvf": calculate_water_fvf(temperature),
            "water_viscosity": calculate_water_viscosity(temperature),
            "gas_fvf": 0.005,
            "gas_viscosity": 0.02,
            "z_factor": 0.8,
            "solution_gor": 0.0
        }
    
    # Get water properties directly from the water_props module
    # since they might not be in the PVT result
    water_fvf = calculate_water_fvf(temperature)
    water_viscosity = calculate_water_viscosity(temperature)
    
    # Get gas viscosity - use a default if not available
    gas_viscosity = getattr(pvt_result, "gas_viscosity", 0.02)
    
    # Convert from PVT result to the expected format for hydraulics
    # Use getattr with defaults for attributes that might be missing
    return {
        "oil_fvf": getattr(pvt_result, "bo", 1.1),
        "oil_viscosity": getattr(pvt_result, "mu_o", 1.0),
        "water_fvf": water_fvf,
        "water_viscosity": water_viscosity,
        "gas_fvf": getattr(pvt_result, "bg", 0.005),
        "gas_viscosity": gas_viscosity,
        "z_factor": getattr(pvt_result, "z", 0.8),
        "solution_gor": getattr(pvt_result, "rs", 0.0)
    }