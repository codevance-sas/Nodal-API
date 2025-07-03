# backend/app/services/hydraulics/engine.py
import numpy as np
import copy
from typing import Dict, Any, List, Optional, Literal, Tuple

from app.schemas.hydraulics import (
    HydraulicsInput, HydraulicsResult, PressurePoint, 
    FlowPatternEnum, FlowPatternResult
)

from .utils import calculate_fluid_properties

# Import from correlations
from .correlations import (
    calculate_hagedorn_brown,
    calculate_beggs_brill,
    calculate_duns_ross,
    calculate_chokshi,
    calculate_orkiszewski,
    calculate_gray,
    calculate_mukherjee_brill,
    calculate_aziz,
    calculate_hasan_kabir,
    calculate_ansari
)

# Import gas specific correlations
# These would be placed in the correlations directory
from .correlations.weymouth import (
    calculate_weymouth, 
    calculate_max_flow_rate,
    calculate_diameter_weymouth
)
from .correlations.panhandle import (
    calculate_panhandle_a, 
    calculate_panhandle_b, 
    calculate_max_flow_rate_panhandle, 
    calculate_diameter_panhandle
)

# Import compressor calculation functions
from .extensions.compressor import (
    calculate_compressor_requirements,
    calculate_optimal_stages,
    joule_thomson_cooling,
    critical_flow_calculation
)


def calculate_hydraulics(data: HydraulicsInput) -> HydraulicsResult:
    """
    Main function to calculate hydraulics based on selected method.
    This is the primary entry point for the hydraulics module.
    """
    method = data.method.lower()
    
    # Check if we need to calculate bottomhole pressure from target
    if data.bhp_mode == "target" and data.target_bhp is not None:
        return calculate_from_target_bhp(data)
    
    # Standard calculation from surface to bottomhole
    if method == "hagedorn-brown":
        return calculate_hagedorn_brown(data)
    elif method == "beggs-brill":
        return calculate_beggs_brill(data)
    elif method == "duns-ross":
        return calculate_duns_ross(data)
    elif method == "chokshi":
        return calculate_chokshi(data)
    elif method == "orkiszewski":
        return calculate_orkiszewski(data)
    elif method == "gray":
        return calculate_gray(data)
    elif method == "mukherjee-brill":
        return calculate_mukherjee_brill(data)
    elif method == "aziz":
        return calculate_aziz(data)
    elif method == "hasan-kabir":
        return calculate_hasan_kabir(data)
    elif method == "ansari":
        return calculate_ansari(data)
    else:
        raise ValueError(f"Unknown method: {method}")


def calculate_from_target_bhp(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile and surface pressure given a target bottomhole pressure.
    Uses iterative approach to match the target BHP.
    """
    # Create a copy of the input data for calculation
    calc_data = copy.deepcopy(data)
    calc_data.bhp_mode = "calculate"  # Switch to calculation mode
    
    # Initial guess for surface pressure (50% of target BHP as starting point)
    calc_data.surface_pressure = data.target_bhp * 0.5
    
    # Maximum iterations and tolerance
    max_iterations = 20
    tolerance = 5.0  # psi
    
    # Store pressure values for each iteration
    surface_pressures = [calc_data.surface_pressure]
    bhp_values = []
    
    # Iterative calculation
    for i in range(max_iterations):
        # Calculate using the current surface pressure
        result = calculate_hydraulics(calc_data)
        
        # Store the result
        bhp_values.append(result.bottomhole_pressure)
        
        # Check if we're close enough to target
        error = result.bottomhole_pressure - data.target_bhp
        if abs(error) < tolerance:
            # We've reached the target within tolerance
            # Add target BHP to result
            result.target_bhp = data.target_bhp
            return result
            
        # Adjust surface pressure using secant method if we have two points
        if i == 0:
            # First iteration - use simple adjustment
            adj_factor = 0.8 if error > 0 else 1.2
            new_pressure = calc_data.surface_pressure * adj_factor
        else:
            # Subsequent iterations - use secant method
            prev_error = bhp_values[-2] - data.target_bhp
            prev_surface = surface_pressures[-1]
            
            if abs(error - prev_error) > 1e-6:  # Avoid division by zero
                # Secant formula: x_n+1 = x_n - f(x_n)*(x_n - x_n-1)/(f(x_n) - f(x_n-1))
                new_pressure = calc_data.surface_pressure - error * (calc_data.surface_pressure - prev_surface) / (error - prev_error)
            else:
                # If we're getting the same error, try a binary search approach
                new_pressure = (calc_data.surface_pressure + prev_surface) / 2
            
        # Ensure surface pressure remains positive and reasonable
        new_pressure = max(50.0, min(data.target_bhp * 0.9, new_pressure))
        
        # Update and store the new surface pressure
        calc_data.surface_pressure = new_pressure
        surface_pressures.append(new_pressure)
    
    # If we've reached the maximum iterations, return the last result
    # Add target BHP to result
    result.target_bhp = data.target_bhp
    return result


def compare_methods(data: HydraulicsInput, methods: List[str] = None) -> Dict[str, Any]:
    """
    Compare results from different hydraulics correlations.
    
    Args:
        data: Input data for hydraulics calculations
        methods: List of methods to compare. If None, all available methods are used.
        
    Returns:
        Dictionary with comparison results
    """
    if methods is None:
        methods = [
            "hagedorn-brown", "beggs-brill", "duns-ross", "chokshi",
            "orkiszewski", "gray", "mukherjee-brill", "aziz",
            "hasan-kabir", "ansari"
        ]
    
    results = {}
    
    for method in methods:
        # Create a copy of the data with the current method
        method_data = copy.deepcopy(data)
        method_data.method = method
        
        # Calculate results for this method
        try:
            result = calculate_hydraulics(method_data)
            results[method] = {
                "bottomhole_pressure": result.bottomhole_pressure,
                "overall_pressure_drop": result.overall_pressure_drop,
                "elevation_percentage": result.elevation_drop_percentage,
                "friction_percentage": result.friction_drop_percentage,
                "acceleration_percentage": result.acceleration_drop_percentage,
                "success": True
            }
        except Exception as e:
            results[method] = {
                "error": str(e),
                "success": False
            }
    
    # Calculate statistics
    successful_methods = [m for m in results if results[m]["success"]]
    if successful_methods:
        bhp_values = [results[m]["bottomhole_pressure"] for m in successful_methods]
        avg_bhp = sum(bhp_values) / len(bhp_values)
        min_bhp = min(bhp_values)
        max_bhp = max(bhp_values)
        std_bhp = np.std(bhp_values) if len(bhp_values) > 1 else 0
        
        statistics = {
            "average_bhp": avg_bhp,
            "min_bhp": min_bhp,
            "max_bhp": max_bhp,
            "std_bhp": std_bhp,
            "bhp_range": max_bhp - min_bhp,
            "percent_range": (max_bhp - min_bhp) / avg_bhp * 100 if avg_bhp > 0 else 0
        }
    else:
        statistics = {
            "error": "No successful calculations"
        }
    
    return {
        "method_results": results,
        "statistics": statistics
    }


def recommend_method(data: HydraulicsInput) -> str:
    """
    Recommend the most appropriate hydraulics correlation based on input parameters.
    
    Args:
        data: Input data for hydraulics calculations
        
    Returns:
        Name of recommended method
    """
    # Extract key parameters for decision
    deviation = data.wellbore_geometry.deviation
    tubing_id = data.wellbore_geometry.tubing_id
    depth = data.wellbore_geometry.depth
    
    # Calculate GLR (Gas-Liquid Ratio)
    total_liquid = data.fluid_properties.oil_rate + data.fluid_properties.water_rate
    if total_liquid > 0:
        glr = data.fluid_properties.gas_rate * 1000 / total_liquid
    else:
        glr = float('inf')  # Infinite GLR for gas-only wells
    
    # Decision logic
    if deviation > 45:
        # Highly deviated well
        if glr > 5000:
            # High GLR deviated well
            return "mukherjee-brill"
        else:
            # Lower GLR deviated well
            return "beggs-brill"
    else:
        # Near-vertical well
        if glr > 10000:
            # Very high GLR (gas wells)
            return "gray"
        elif glr > 2000:
            # Moderate to high GLR
            return "duns-ross"
        elif tubing_id > 3.5:
            # Large diameter tubing
            return "orkiszewski"
        elif depth > 10000:
            # Deep well
            return "hagedorn-brown"
        else:
            # Standard well
            return "hagedorn-brown"


def flow_rate_sensitivity(data, min_oil_rate, max_oil_rate, steps, water_cut, gor):
    """
    Perform sensitivity analysis on flow rates
    """
    # Calculate oil rates to evaluate
    oil_rates = np.linspace(min_oil_rate, max_oil_rate, steps)
    
    results = []
    for oil_rate in oil_rates:
        # Create modified input data
        input_data = copy.deepcopy(data)
        input_data.fluid_properties.oil_rate = oil_rate
        input_data.fluid_properties.water_rate = oil_rate * water_cut / (1 - water_cut) if water_cut < 1 else 0
        input_data.fluid_properties.gas_rate = oil_rate * gor / 1000  # Convert to Mscf/d
        
        # Calculate result
        result = calculate_hydraulics(input_data)
        
        # Store key data
        results.append({
            "oil_rate": oil_rate,
            "total_liquid_rate": oil_rate + input_data.fluid_properties.water_rate,
            "bhp": result.bottomhole_pressure,
            "pressure_drop": result.overall_pressure_drop,
            "elevation_pct": result.elevation_drop_percentage,
            "friction_pct": result.friction_drop_percentage
        })
    
    return {
        "sensitivity_type": "flow_rate",
        "results": results
    }


def tubing_sensitivity(data, min_tubing_id, max_tubing_id, steps):
    """
    Perform sensitivity analysis on tubing diameter
    """
    # Calculate tubing sizes to evaluate
    tubing_sizes = np.linspace(min_tubing_id, max_tubing_id, steps)
    
    results = []
    for tubing_id in tubing_sizes:
        # Create modified input data
        input_data = copy.deepcopy(data)
        input_data.wellbore_geometry.tubing_id = tubing_id
        
        # Calculate result
        result = calculate_hydraulics(input_data)
        
        # Calculate effective flow area
        flow_area = np.pi * (tubing_id/24)**2  # ft²
        
        # Store key data
        results.append({
            "tubing_id": tubing_id,
            "flow_area": flow_area,
            "bhp": result.bottomhole_pressure,
            "pressure_drop": result.overall_pressure_drop,
            "elevation_pct": result.elevation_drop_percentage,
            "friction_pct": result.friction_drop_percentage
        })
    
    return {
        "sensitivity_type": "tubing_size",
        "results": results
    }


def get_example_input() -> HydraulicsInput:
    """
    Return an example input for the hydraulics calculation
    """
    return HydraulicsInput(
        fluid_properties={
            "oil_rate": 500.0,
            "water_rate": 100.0,
            "gas_rate": 1000.0,
            "oil_gravity": 35.0,
            "water_gravity": 1.05,
            "gas_gravity": 0.65,
            "bubble_point": 2500.0,
            "temperature_gradient": 0.015,
            "surface_temperature": 75.0
        },
        wellbore_geometry={
            "pipe_segments": [
                {
                    "start_depth": 0.0,
                    "end_depth": 10000.0,
                    "diameter": 2.441
                },
                {
                    "start_depth": 10000.0,
                    "end_depth": 20000.0,
                    "diameter": 2
                }
            ],
            "deviation": 0.0,
            "roughness": 0.0006,
            "depth_steps": 100
        },
        method="hagedorn-brown",
        surface_pressure=100.0,
        bhp_mode="calculate"
    )


# New functions for gas pipeline calculations

def calculate_gas_pipeline(
    diameter: float,              # pipe diameter, inches
    length: float,                # pipe length, ft
    gas_rate: float,              # gas flow rate, Mscf/d
    inlet_pressure: float,        # inlet pressure, psia  
    gas_gravity: float,           # gas specific gravity (air=1)
    temperature: float,           # average gas temperature, °F
    method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth",
    z_factor: Optional[float] = None,  # gas compressibility factor
    efficiency: float = 0.95,     # pipe efficiency factor (0.5-1.0)
    elevation_change: float = 0.0,  # elevation change (ft), positive for uphill
    co2_fraction: float = 0.0,    # CO2 mole fraction
    h2s_fraction: float = 0.0,    # H2S mole fraction
    n2_fraction: float = 0.0      # N2 mole fraction
) -> Dict[str, Any]:
    """
    Calculate gas pipeline pressure drop using specified correlation.
    
    Args:
        diameter: Pipe inside diameter in inches
        length: Pipe length in feet
        gas_rate: Gas flow rate in Mscf/d
        inlet_pressure: Inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        method: Calculation method to use
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipe efficiency factor (0.5-1.0)
        elevation_change: Elevation change in feet (positive for uphill)
        co2_fraction: CO2 mole fraction
        h2s_fraction: H2S mole fraction
        n2_fraction: N2 mole fraction
        
    Returns:
        Dictionary with calculated results including outlet pressure
    """
    # Calculate hydrostatic pressure effect due to elevation change
    if elevation_change != 0:
        # Calculate average pressure (first approximation)
        avg_pressure = inlet_pressure * 0.85  # Rough estimate
        
        # Calculate average temperature in Rankine
        avg_temp_r = temperature + 460
        
        # Calculate z-factor if not provided
        if z_factor is None:
            # Simple z-factor correlation
            p_pc = 756.8 - 131.0 * gas_gravity - 3.6 * gas_gravity**2
            t_pc = 169.2 + 349.5 * gas_gravity - 74.0 * gas_gravity**2
            
            # Adjustment for acid gases and nitrogen
            p_pc -= 9.5 * co2_fraction + 5.2 * h2s_fraction - 0.1 * n2_fraction
            t_pc -= 3.5 * co2_fraction + 4.8 * h2s_fraction - 7.9 * n2_fraction
            
            p_pr = avg_pressure / p_pc
            t_pr = avg_temp_r / t_pc
            z_factor = 1.0 - 0.06 * p_pr / t_pr  # simplified correlation
        
        # Calculate gas density (lb/ft³)
        gas_density = 0.0764 * gas_gravity * avg_pressure / (z_factor * avg_temp_r)
        
        # Calculate hydrostatic pressure change (psi)
        # ΔP = ρgh / 144 (to convert from lb/ft² to psi)
        hydrostatic_change = gas_density * elevation_change / 144
    else:
        hydrostatic_change = 0.0
    
    # Select and calculate using specified method
    if method.lower() == "weymouth":
        # Calculate using Weymouth equation
        result = calculate_weymouth(
            diameter=diameter,
            length=length,
            gas_rate=gas_rate,
            inlet_pressure=inlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )
    elif method.lower() == "panhandle_a":
        # Calculate using Panhandle A
        result = calculate_panhandle_a(
            diameter=diameter,
            length=length,
            gas_rate=gas_rate,
            inlet_pressure=inlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )
    elif method.lower() == "panhandle_b":
        # Calculate using Panhandle B
        result = calculate_panhandle_b(
            diameter=diameter,
            length=length,
            gas_rate=gas_rate,
            inlet_pressure=inlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Add elevation effect to outlet pressure
    result["outlet_pressure"] -= hydrostatic_change
    result["pressure_drop"] += hydrostatic_change
    
    # Add elevation component information
    result["elevation_component"] = hydrostatic_change
    result["friction_component"] = result["pressure_drop"] - hydrostatic_change
    
    # Calculate temperature effects (Joule-Thomson cooling)
    jt_results = joule_thomson_cooling(
        inlet_pressure=inlet_pressure,
        outlet_pressure=result["outlet_pressure"],
        inlet_temperature=temperature,
        gas_gravity=gas_gravity,
        co2_fraction=co2_fraction,
        h2s_fraction=h2s_fraction,
        n2_fraction=n2_fraction
    )
    
    # Add temperature effects to results
    result["inlet_temperature"] = temperature
    result["outlet_temperature"] = jt_results["outlet_temperature"]
    result["temperature_drop"] = jt_results["temperature_drop"]
    result["hydrate_risk"] = jt_results["hydrate_risk"]
    result["hydrate_formation_temp"] = jt_results["hydrate_formation_temp"]
    
    # Add additional input parameters to result for reference
    result["diameter"] = diameter
    result["length"] = length
    result["gas_rate"] = gas_rate
    result["gas_gravity"] = gas_gravity
    result["method"] = method
    result["elevation_change"] = elevation_change
    
    return result


def calculate_gas_pipeline_diameter(
    gas_rate: float,              # gas flow rate, Mscf/d
    length: float,                # pipe length, ft
    inlet_pressure: float,        # inlet pressure, psia
    outlet_pressure: float,       # outlet pressure, psia
    gas_gravity: float,           # gas specific gravity (air=1)
    temperature: float,           # average gas temperature, °F
    method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth",
    z_factor: Optional[float] = None,  # gas compressibility factor
    efficiency: float = 0.95,     # pipe efficiency factor (0.5-1.0)
    available_sizes: Optional[List[float]] = None,  # optional list of available pipe sizes
    velocity_limit: float = 60.0  # maximum allowable velocity (ft/s)
) -> Dict[str, Any]:
    """
    Calculate required pipe diameter for gas pipeline.
    
    Args:
        gas_rate: Gas flow rate in Mscf/d
        length: Pipe length in feet
        inlet_pressure: Inlet pressure in psia
        outlet_pressure: Outlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        method: Calculation method to use
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipe efficiency factor (0.5-1.0)
        available_sizes: List of available pipe diameters (inches)
        velocity_limit: Maximum allowable gas velocity (ft/s)
        
    Returns:
        Dictionary with calculated results including recommended diameter
    """
    # Default available sizes if not provided
    if available_sizes is None:
        available_sizes = [2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0, 30.0, 36.0]
    
    # Select method and calculate required diameter
    if method.lower() == "weymouth":
        calc_diameter = calculate_diameter_weymouth(
            gas_rate=gas_rate,
            length=length,
            inlet_pressure=inlet_pressure,
            outlet_pressure=outlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )
    elif method.lower() in ["panhandle_a", "panhandle_b"]:
        calc_diameter = calculate_diameter_panhandle(
            equation="a" if method.lower() == "panhandle_a" else "b",
            gas_rate=gas_rate,
            length=length,
            inlet_pressure=inlet_pressure,
            outlet_pressure=outlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Find nearest available size (equal or larger)
    available_gte = [d for d in available_sizes if d >= calc_diameter]
    if available_gte:
        recommended_diameter = min(available_gte)
    else:
        # No larger size available, use largest available
        recommended_diameter = max(available_sizes)
    
    # Check velocity constraints for recommended diameter
    # Start with recommended diameter and increase if velocity is too high
    final_diameter = recommended_diameter
    velocity_ok = False
    
    while not velocity_ok:
        # Calculate flow for the selected diameter
        if method.lower() == "weymouth":
            flow_result = calculate_weymouth(
                diameter=final_diameter,
                length=length,
                gas_rate=gas_rate,
                inlet_pressure=inlet_pressure,
                gas_gravity=gas_gravity,
                temperature=temperature,
                z_factor=z_factor,
                efficiency=efficiency
            )
        elif method.lower() == "panhandle_a":
            flow_result = calculate_panhandle_a(
                diameter=final_diameter,
                length=length,
                gas_rate=gas_rate,
                inlet_pressure=inlet_pressure,
                gas_gravity=gas_gravity,
                temperature=temperature,
                z_factor=z_factor,
                efficiency=efficiency
            )
        else:  # panhandle_b
            flow_result = calculate_panhandle_b(
                diameter=final_diameter,
                length=length,
                gas_rate=gas_rate,
                inlet_pressure=inlet_pressure,
                gas_gravity=gas_gravity,
                temperature=temperature,
                z_factor=z_factor,
                efficiency=efficiency
            )
        
        # Check if velocity is acceptable
        if flow_result["flow_velocity"] <= velocity_limit:
            velocity_ok = True
        else:
            # Find next larger size
            larger_sizes = [d for d in available_sizes if d > final_diameter]
            if not larger_sizes:
                # No larger sizes available, warn in the results
                velocity_ok = True  # Break the loop
            else:
                final_diameter = min(larger_sizes)
    
    # Prepare result
    result = {
        "calculated_diameter": calc_diameter,
        "recommended_diameter": recommended_diameter,
        "final_diameter": final_diameter,
        "flow_velocity": flow_result["flow_velocity"] if 'flow_result' in locals() else None,
        "velocity_limit": velocity_limit,
        "velocity_limited": recommended_diameter != final_diameter,
        "method": method,
        "available_sizes": available_sizes,
        "calculation_parameters": {
            "gas_rate": gas_rate,
            "length": length,
            "inlet_pressure": inlet_pressure,
            "outlet_pressure": outlet_pressure,
            "gas_gravity": gas_gravity,
            "temperature": temperature,
            "efficiency": efficiency
        }
    }
    
    return result


def gas_pipeline_sensitivity(
    base_diameter: float,         # base pipe diameter, inches
    base_length: float,           # base pipe length, ft
    base_gas_rate: float,         # base gas flow rate, Mscf/d
    base_inlet_pressure: float,   # base inlet pressure, psia
    gas_gravity: float,           # gas specific gravity (air=1)
    temperature: float,           # average gas temperature, °F
    method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth",
    variable: Literal["diameter", "length", "flow_rate", "pressure"] = "flow_rate",
    min_value: float = None,      # minimum value for the variable
    max_value: float = None,      # maximum value for the variable
    steps: int = 10,              # number of steps for sensitivity analysis
    z_factor: Optional[float] = None,  # gas compressibility factor
    efficiency: float = 0.95      # pipe efficiency factor (0.5-1.0)
) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on gas pipeline design parameters.
    
    Args:
        base_diameter: Base pipe diameter in inches
        base_length: Base pipe length in feet
        base_gas_rate: Base gas flow rate in Mscf/d
        base_inlet_pressure: Base inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        method: Calculation method to use
        variable: Parameter to vary in sensitivity analysis
        min_value: Minimum value for the variable
        max_value: Maximum value for the variable
        steps: Number of steps for sensitivity analysis
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipe efficiency factor (0.5-1.0)
        
    Returns:
        Dictionary with sensitivity analysis results
    """
    # Set up default ranges if not provided
    if variable == "diameter":
        if min_value is None:
            min_value = max(1.0, 0.5 * base_diameter)
        if max_value is None:
            max_value = 2.0 * base_diameter
        values = np.linspace(min_value, max_value, steps)
        param_name = "diameter"
    
    elif variable == "length":
        if min_value is None:
            min_value = max(100.0, 0.1 * base_length)
        if max_value is None:
            max_value = 3.0 * base_length
        values = np.linspace(min_value, max_value, steps)
        param_name = "length"
    
    elif variable == "flow_rate":
        if min_value is None:
            min_value = max(10.0, 0.2 * base_gas_rate)
        if max_value is None:
            max_value = 2.0 * base_gas_rate
        values = np.linspace(min_value, max_value, steps)
        param_name = "gas_rate"
    
    elif variable == "pressure":
        if min_value is None:
            min_value = max(100.0, 0.5 * base_inlet_pressure)
        if max_value is None:
            max_value = 2.0 * base_inlet_pressure
        values = np.linspace(min_value, max_value, steps)
        param_name = "inlet_pressure"
    
    else:
        raise ValueError(f"Unknown sensitivity parameter: {variable}")
    
    # Perform calculations for each value
    results = []
    
    for value in values:
        # Set up parameters for this iteration
        params = {
            "diameter": base_diameter,
            "length": base_length,
            "gas_rate": base_gas_rate,
            "inlet_pressure": base_inlet_pressure,
            "gas_gravity": gas_gravity,
            "temperature": temperature,
            "z_factor": z_factor,
            "efficiency": efficiency,
            "method": method
        }
        
        # Update the parameter being varied
        params[param_name] = value
        
        # Calculate result
        result = calculate_gas_pipeline(**params)
        
        # Extract key results
        results.append({
            param_name: value,
            "outlet_pressure": result["outlet_pressure"],
            "pressure_drop": result["pressure_drop"],
            "flow_velocity": result["flow_velocity"],
            "temperature_drop": result.get("temperature_drop", 0.0),
            "hydrate_risk": result.get("hydrate_risk", False)
        })
    
    # Return sensitivity results
    return {
        "sensitivity_type": variable,
        "results": results,
        "base_parameters": {
            "diameter": base_diameter,
            "length": base_length,
            "gas_rate": base_gas_rate,
            "inlet_pressure": base_inlet_pressure,
            "gas_gravity": gas_gravity,
            "temperature": temperature,
            "method": method
        }
    }


def calculate_compressor_station(
    inlet_pressure: float,       # inlet pressure, psia
    outlet_pressure: float,      # required outlet pressure, psia
    gas_rate: float,             # gas flow rate, MMscf/d
    gas_gravity: float,          # gas specific gravity (air=1)
    inlet_temperature: float,    # inlet temperature, °F
    compressor_type: Literal["centrifugal", "reciprocating"] = "centrifugal",
    max_ratio_per_stage: float = 3.0,  # max compression ratio per stage
    efficiency: float = 0.75,    # adiabatic efficiency
    z_avg: Optional[float] = None,     # average compressibility factor
    k: Optional[float] = None          # specific heat ratio cp/cv
) -> Dict[str, Any]:
    """
    Calculate compressor station requirements for gas pipeline.
    
    Args:
        inlet_pressure: Compressor inlet pressure in psia
        outlet_pressure: Required outlet pressure in psia
        gas_rate: Gas flow rate in MMscf/d
        gas_gravity: Gas specific gravity relative to air
        inlet_temperature: Gas temperature at compressor inlet in °F
        compressor_type: Type of compressor ("centrifugal" or "reciprocating")
        max_ratio_per_stage: Maximum compression ratio per stage
        efficiency: Adiabatic efficiency as fraction
        z_avg: Average gas compressibility factor (optional)
        k: Specific heat ratio (cp/cv), calculated if None
        
    Returns:
        Dictionary with compressor station design parameters
    """
    # Calculate optimal number of stages
    stages = calculate_optimal_stages(inlet_pressure, outlet_pressure, max_ratio_per_stage)
    
    # Calculate compressor requirements
    comp_results = calculate_compressor_requirements(
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_rate=gas_rate,
        gas_gravity=gas_gravity,
        inlet_temperature=inlet_temperature,
        z_avg=z_avg,
        k=k,
        compressor_type=compressor_type,
        stages=stages,
        efficiency=efficiency
    )
    
    # Check for potential JT cooling effects after compression
    # Gas will be cooler after traveling through the pipeline
    pipeline_cooling = joule_thomson_cooling(
        inlet_pressure=outlet_pressure,
        outlet_pressure=outlet_pressure * 0.7,  # Assume 30% pressure drop in pipeline
        inlet_temperature=comp_results["discharge_temperature_f"],
        gas_gravity=gas_gravity
    )
    
    # Add JT cooling info to results
    comp_results["pipeline_cooling"] = pipeline_cooling
    
    # Add economic estimates
    # Calculate installed cost (rough estimate in USD)
    if compressor_type == "centrifugal":
        # Centrifugal: $2,000-3,000 per HP
        installed_cost = comp_results["power_required_hp"] * 2500
    else:
        # Reciprocating: $1,500-2,500 per HP
        installed_cost = comp_results["power_required_hp"] * 2000
    
    # Add 20% for auxiliaries
    installed_cost *= 1.2
    
    # Add economic data
    comp_results["economics"] = {
        "estimated_installed_cost_usd": installed_cost,
        "annual_fuel_cost_usd": comp_results["fuel_consumption_mmscfd"] * 365 * 4.0 * 1000,  # Assuming $4/MMBtu
        "annual_maintenance_cost_usd": installed_cost * 0.05  # 5% of installed cost per year
    }
    
    return comp_results


def design_gas_lift_system(
    wellhead_pressure: float,     # wellhead pressure, psia
    wellhead_temperature: float,  # wellhead temperature, °F
    gas_injection_depth: float,   # gas injection depth, ft
    liquid_rate: float,           # liquid production rate, STB/d
    water_cut: float,             # water cut, fraction
    formation_pressure: float,    # formation pressure, psia
    gas_gravity: float,           # gas specific gravity (air=1)
    tubing_id: float,             # tubing inner diameter, inches
    casing_id: float,             # casing inner diameter, inches
    valve_ports: List[Tuple[float, float]] = None,  # list of (depth, port size) for valves
    method: str = "beggs-brill"   # hydraulics calculation method
) -> Dict[str, Any]:
    """
    Design a gas lift system for artificial lift in oil wells.
    
    Args:
        wellhead_pressure: Pressure at wellhead in psia
        wellhead_temperature: Temperature at wellhead in °F
        gas_injection_depth: Depth of gas injection in feet
        liquid_rate: Liquid production rate in STB/d
        water_cut: Water cut as fraction
        formation_pressure: Formation pressure in psia
        gas_gravity: Gas specific gravity relative to air
        tubing_id: Tubing inner diameter in inches
        casing_id: Casing inner diameter in inches
        valve_ports: List of (depth, port size) tuples for gas lift valves
        method: Hydraulics calculation method
        
    Returns:
        Dictionary with gas lift design parameters
    """
    # If no valve ports provided, create a default design
    if valve_ports is None:
        # Create equally spaced valves from surface to injection depth
        num_valves = 5
        depths = np.linspace(500, gas_injection_depth, num_valves)
        port_sizes = [1/16, 1/8, 3/16, 1/4, 5/16]  # Increasing port sizes with depth
        valve_ports = [(depths[i], port_sizes[i]) for i in range(num_valves)]
    
    # Calculate pressure and temperature gradients
    temp_gradient = (formation_pressure - wellhead_temperature) / gas_injection_depth
    
    # Calculate oil and water rates
    oil_rate = liquid_rate * (1 - water_cut)
    water_rate = liquid_rate * water_cut
    
    # Create hydraulics input for natural flow (without gas lift)
    natural_flow_input = HydraulicsInput(
        fluid_properties={
            "oil_rate": oil_rate,
            "water_rate": water_rate,
            "gas_rate": 0.0,  # No gas initially
            "oil_gravity": 35.0,  # Assumed oil gravity
            "water_gravity": 1.05,
            "gas_gravity": gas_gravity,
            "bubble_point": 2000.0,  # Assumed bubble point
            "temperature_gradient": temp_gradient,
            "surface_temperature": wellhead_temperature
        },
        wellbore_geometry={
            "depth": gas_injection_depth,
            "deviation": 0.0,  # Assumed vertical well
            "tubing_id": tubing_id,
            "roughness": 0.0006,
            "depth_steps": 100
        },
        method=method,
        surface_pressure=wellhead_pressure,
        bhp_mode="calculate"
    )
    
    # Calculate natural flow BHP
    natural_flow_result = calculate_hydraulics(natural_flow_input)
    natural_flow_bhp = natural_flow_result.bottomhole_pressure
    
    # Determine if gas lift is needed
    gas_lift_needed = natural_flow_bhp > formation_pressure
    
    # If gas lift is needed, determine required gas injection rate
    gas_rates = []
    bhp_values = []
    
    if gas_lift_needed:
        # Try different gas rates to find optimal
        test_gas_rates = np.linspace(100, 2000, 10)  # Mscf/d
        
        for gas_rate in test_gas_rates:
            # Create hydraulics input with gas lift
            gas_lift_input = copy.deepcopy(natural_flow_input)
            gas_lift_input.fluid_properties.gas_rate = gas_rate
            
            # Calculate BHP with gas lift
            try:
                gas_lift_result = calculate_hydraulics(gas_lift_input)
                gas_rates.append(gas_rate)
                bhp_values.append(gas_lift_result.bottomhole_pressure)
            except Exception as e:
                # Skip failed calculations
                continue
    
    # Find optimal gas rate (where BHP just below formation pressure)
    optimal_gas_rate = 0.0
    if gas_lift_needed and gas_rates:
        # Find gas rate where BHP is just below formation pressure
        for i, bhp in enumerate(bhp_values):
            if bhp < formation_pressure:
                optimal_gas_rate = gas_rates[i]
                optimal_bhp = bhp
                break
        
        # If no gas rate gives BHP below formation pressure, use max rate
        if optimal_gas_rate == 0.0:
            optimal_gas_rate = gas_rates[-1]
            optimal_bhp = bhp_values[-1]
    
    # Calculate valve operating pressures
    valve_data = []
    if gas_lift_needed:
        # Create hydraulics input with optimal gas lift
        optimal_input = copy.deepcopy(natural_flow_input)
        optimal_input.fluid_properties.gas_rate = optimal_gas_rate
        
        # Calculate hydraulics with optimal gas lift
        optimal_result = calculate_hydraulics(optimal_input)
        
        # Get pressure profile
        pressure_profile = optimal_result.pressure_profile
        
        # Calculate valve pressures
        for depth, port_size in valve_ports:
            # Find closest point in pressure profile
            idx = np.argmin([abs(p.depth - depth) for p in pressure_profile])
            tubing_pressure = pressure_profile[idx].pressure
            
            # Calculate casing pressure (simplified)
            # Assume gas column from surface to valve
            avg_temp_r = wellhead_temperature + temp_gradient * depth/2 + 460
            avg_casing_pressure = wellhead_pressure * 1.5  # Simplified assumption
            
            # Calculate gas density
            if z_factor is None:
                # Simple z-factor correlation
                p_pc = 756.8 - 131.0 * gas_gravity - 3.6 * gas_gravity**2
                t_pc = 169.2 + 349.5 * gas_gravity - 74.0 * gas_gravity**2
                p_pr = avg_casing_pressure / p_pc
                t_pr = avg_temp_r / t_pc
                z_factor = 1.0 - 0.06 * p_pr / t_pr  # simplified correlation
            
            # Calculate gas density in casing
            gas_density = 0.0764 * gas_gravity * avg_casing_pressure / (z_factor * avg_temp_r)
            
            # Calculate casing pressure at valve depth
            casing_pressure = wellhead_pressure + (gas_density * depth / 144)
            
            # Calculate valve differential pressure
            differential = casing_pressure - tubing_pressure
            
            valve_data.append({
                "depth": depth,
                "port_size": port_size,
                "tubing_pressure": tubing_pressure,
                "casing_pressure": casing_pressure,
                "differential_pressure": differential
            })
    
    # Prepare results
    result = {
        "natural_flow_possible": not gas_lift_needed,
        "natural_flow_bhp": natural_flow_bhp,
        "formation_pressure": formation_pressure,
        "optimal_gas_rate": optimal_gas_rate if gas_lift_needed else 0.0,
        "optimal_bhp": optimal_bhp if gas_lift_needed else natural_flow_bhp,
        "valve_data": valve_data,
        "input_parameters": {
            "wellhead_pressure": wellhead_pressure,
            "wellhead_temperature": wellhead_temperature,
            "gas_injection_depth": gas_injection_depth,
            "liquid_rate": liquid_rate,
            "water_cut": water_cut,
            "tubing_id": tubing_id,
            "casing_id": casing_id,
            "method": method
        }
    }
    
    # Calculate compression requirements if gas lift needed
    if gas_lift_needed:
        # Assume compressor outlet pressure is 1.5 times the wellhead pressure
        compressor_outlet = wellhead_pressure * 1.5
        
        # Assume inlet pressure is half of wellhead pressure (simplified)
        compressor_inlet = wellhead_pressure * 0.5
        
        # Calculate compressor requirements
        compressor_result = calculate_compressor_requirements(
            inlet_pressure=compressor_inlet,
            outlet_pressure=compressor_outlet,
            gas_rate=optimal_gas_rate / 1000,  # Convert from Mscf/d to MMscf/d
            gas_gravity=gas_gravity,
            inlet_temperature=wellhead_temperature,
            compressor_type="reciprocating",  # Typical for gas lift
            stages=calculate_optimal_stages(compressor_inlet, compressor_outlet),
            efficiency=0.75
        )
        
        # Add compressor data to results
        result["compressor_data"] = compressor_result
    
    return result


def design_gas_gathering_system(
    well_data: List[Dict[str, Any]],  # list of well data dictionaries
    central_facility_location: Tuple[float, float],  # (x, y) coordinates
    pipeline_method: Literal["weymouth", "panhandle_a", "panhandle_b"] = "weymouth",
    gas_gravity: float = 0.65,  # gas specific gravity (air=1)
    temperature: float = 80.0,  # average temperature, °F
    min_pressure: float = 100.0  # minimum allowed pressure, psia
) -> Dict[str, Any]:
    """
    Design a gas gathering system connecting multiple wells to a central facility.
    
    Args:
        well_data: List of well data dictionaries with properties:
                   {"id": str, "location": (x, y), "gas_rate": float, "pressure": float}
        central_facility_location: (x, y) coordinates of central facility
        pipeline_method: Calculation method for pipelines
        gas_gravity: Gas specific gravity relative to air
        temperature: Average temperature in °F
        min_pressure: Minimum allowed pressure in psia
        
    Returns:
        Dictionary with gas gathering system design
    """
    # Validate inputs
    if not well_data:
        raise ValueError("No well data provided")
    
    # Initialize results
    pipelines = []
    compressor_stations = []
    total_length = 0.0
    total_gas_rate = 0.0
    
    # Group wells by proximity (simple clustering)
    # For this example, we'll use a simple trunk line design
    # More sophisticated designs would use optimization algorithms
    
    # Sort wells by distance to central facility
    for well in well_data:
        # Calculate distance to central facility
        x_well, y_well = well["location"]
        x_cf, y_cf = central_facility_location
        distance = np.sqrt((x_well - x_cf)**2 + (y_well - y_cf)**2)
        well["distance_to_cf"] = distance
    
    # Sort wells by distance
    sorted_wells = sorted(well_data, key=lambda w: w["distance_to_cf"])
    
    # Design trunk line from farthest well to central facility
    trunk_well = sorted_wells[-1]
    trunk_points = [trunk_well["location"], central_facility_location]
    trunk_length = trunk_well["distance_to_cf"]
    trunk_gas_rate = trunk_well["gas_rate"]
    trunk_pressure = trunk_well["pressure"]
    
    # Calculate trunk line diameter
    trunk_diameter_result = calculate_gas_pipeline_diameter(
        gas_rate=trunk_gas_rate,
        length=trunk_length,
        inlet_pressure=trunk_pressure,
        outlet_pressure=min_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature,
        method=pipeline_method
    )
    
    trunk_diameter = trunk_diameter_result["final_diameter"]
    
    # Add trunk line to pipelines
    pipelines.append({
        "id": f"trunk_{trunk_well['id']}_to_cf",
        "type": "trunk",
        "connects": [trunk_well["id"], "central_facility"],
        "length": trunk_length,
        "diameter": trunk_diameter,
        "gas_rate": trunk_gas_rate,
        "inlet_pressure": trunk_pressure,
        "outlet_pressure": min_pressure
    })
    
    total_length += trunk_length
    total_gas_rate += trunk_gas_rate
    
    # Connect other wells to trunk line
    for well in sorted_wells[:-1]:
        # Calculate distance to trunk line (simplified - assumes straight line trunk)
        # This is a simplification - real gathering system design would use more sophisticated algorithms
        x_well, y_well = well["location"]
        distance_to_trunk = min_distance_to_line_segment(
            (x_well, y_well),
            trunk_points[0],
            trunk_points[1]
        )
        
        # Design lateral from well to trunk
        lateral_length = distance_to_trunk
        lateral_gas_rate = well["gas_rate"]
        lateral_pressure = well["pressure"]
        
        # Calculate lateral diameter
        lateral_diameter_result = calculate_gas_pipeline_diameter(
            gas_rate=lateral_gas_rate,
            length=lateral_length,
            inlet_pressure=lateral_pressure,
            outlet_pressure=trunk_pressure * 0.95,  # Slightly below trunk pressure
            gas_gravity=gas_gravity,
            temperature=temperature,
            method=pipeline_method
        )
        
        lateral_diameter = lateral_diameter_result["final_diameter"]
        
        # Add lateral to pipelines
        pipelines.append({
            "id": f"lateral_{well['id']}_to_trunk",
            "type": "lateral",
            "connects": [well["id"], f"trunk_{trunk_well['id']}_to_cf"],
            "length": lateral_length,
            "diameter": lateral_diameter,
            "gas_rate": lateral_gas_rate,
            "inlet_pressure": lateral_pressure,
            "outlet_pressure": trunk_pressure * 0.95
        })
        
        total_length += lateral_length
        total_gas_rate += lateral_gas_rate
    
    # Check if compression is needed at central facility
    if min_pressure < 300:  # Typical minimum gathering pressure for processing
        # Design compressor station
        compressor_result = calculate_compressor_station(
            inlet_pressure=min_pressure,
            outlet_pressure=300.0,  # Typical processing pressure
            gas_rate=total_gas_rate / 1000,  # Convert to MMscf/d
            gas_gravity=gas_gravity,
            inlet_temperature=temperature
        )
        
        # Add compressor station
        compressor_stations.append({
            "id": "central_facility_compressor",
            "location": central_facility_location,
            "inlet_pressure": min_pressure,
            "outlet_pressure": 300.0,
            "gas_rate": total_gas_rate,
            "power_required_hp": compressor_result["power_required_hp"],
            "stages": compressor_result["stage_pressures"]["inlet"]
        })
    
    # Prepare results
    result = {
        "pipelines": pipelines,
        "compressor_stations": compressor_stations,
        "total_length_ft": total_length,
        "total_gas_rate_mscfd": total_gas_rate,
        "central_facility": {
            "location": central_facility_location,
            "inlet_pressure": min_pressure,
            "total_gas_rate": total_gas_rate
        },
        "wells": well_data
    }
    
    return result


def min_distance_to_line_segment(point, line_start, line_end):
    """Helper function to calculate minimum distance from point to line segment"""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    # Calculate line segment parameters
    line_length_squared = (x2 - x1)**2 + (y2 - y1)**2
    if line_length_squared == 0:
        # Line segment is actually a point
        return np.sqrt((x - x1)**2 + (y - y1)**2)
    
    # Calculate projection of point onto line segment
    t = max(0, min(1, ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / line_length_squared))
    projection_x = x1 + t * (x2 - x1)
    projection_y = y1 + t * (y2 - y1)
    
    # Calculate distance from point to projection
    return np.sqrt((x - projection_x)**2 + (y - projection_y)**2)