# app/services/hydraulics/correlations/weymouth.py
import numpy as np
import math
from typing import Dict, Any, Optional


def calculate_weymouth(
    diameter: float,     # inside diameter, inches
    length: float,       # pipe length, ft
    gas_rate: float,     # gas flow rate, Mscf/d
    inlet_pressure: float,  # inlet pressure, psia
    gas_gravity: float,  # gas specific gravity (air=1)
    temperature: float,  # average gas temperature, °F
    z_factor: Optional[float] = None,  # gas compressibility factor
    efficiency: float = 1.0,  # pipe efficiency factor (0.5-1.0)
) -> Dict[str, Any]:
    """
    Calculate gas flow in a pipeline using the Weymouth equation.
    
    The Weymouth equation is specifically designed for gas pipelines and is valid for:
    - High-pressure gas flow (completely turbulent)
    - Reynolds numbers > 4000
    - Pipe diameters from 2 to 60 inches
    - Primarily used for transmission pipelines
    
    Args:
        diameter: Pipe inside diameter in inches
        length: Pipe length in feet
        gas_rate: Gas flow rate in Mscf/d
        inlet_pressure: Inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)
        
    Returns:
        Dictionary containing calculated results
    """
    # Convert units as needed
    d = diameter  # inches
    length_miles = length / 5280  # convert feet to miles
    t_avg = temperature + 460  # convert °F to °R
    
    # Calculate z-factor if not provided
    if z_factor is None:
        # Simple z-factor correlation (more accurate methods exist in the PVT module)
        p_avg = inlet_pressure * 0.75  # rough estimate of average pressure
        p_pr = p_avg / (709 - 58 * gas_gravity)  # reduced pressure
        t_pr = t_avg / (170 + 314 * gas_gravity)  # reduced temperature
        z_factor = 1.0 - 0.06 * p_pr / t_pr  # simplified correlation
    
    # Weymouth constant (includes units conversion factors)
    C = 433.5  # for units: Mscf/d, psia, inches, miles, °R
    
    # Calculate outlet pressure using Weymouth equation
    # Formula: Q = (C * E * d^2.667 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5)
    # Rearranged for p2:
    # p2^2 = p1^2 - [(Q * T_avg^0.5 * G^0.5 * L^0.5) / (C * E * d^2.667)]^2
    
    term = (gas_rate * math.sqrt(t_avg * gas_gravity * length_miles)) / (C * efficiency * d**2.667)
    p2_squared = inlet_pressure**2 - term**2
    
    # Ensure we don't have negative pressure (could happen with very high flow rates)
    if p2_squared <= 0:
        outlet_pressure = 14.7  # set to atmospheric if calculation gives invalid result
        pressure_drop = inlet_pressure - outlet_pressure
        is_valid = False
        max_flow = calculate_max_flow_rate(diameter, length, inlet_pressure, gas_gravity, temperature, z_factor, efficiency)
    else:
        outlet_pressure = math.sqrt(p2_squared)
        pressure_drop = inlet_pressure - outlet_pressure
        is_valid = True
        max_flow = None
    
    # Calculate average gas velocity (ft/s)
    avg_pressure = (inlet_pressure + outlet_pressure) / 2
    # Flow area in square feet
    area = math.pi * (d/24)**2
    # Convert Mscf/d to actual ft³/s at average conditions
    actual_flow_rate = gas_rate * 1000 * (14.7/avg_pressure) * (t_avg/520) * z_factor / 86400
    velocity = actual_flow_rate / area
    
    # Calculate Reynolds number
    # Simplified viscosity correlation for natural gas (in centipoise)
    gas_visc = 0.01 + 0.002 * gas_gravity
    # Convert to lb-sec/ft² for Reynolds calculation
    gas_visc_lbft = gas_visc * 6.72e-4
    # Density at average conditions (lb/ft³)
    gas_density = 0.0764 * gas_gravity * avg_pressure / (z_factor * t_avg) * 520/14.7
    # Reynolds number = (density * velocity * diameter) / viscosity
    reynolds = gas_density * velocity * (d/12) / gas_visc_lbft
    
    # Friction factor - Weymouth equation uses a fixed friction factor
    # but we can calculate a more accurate one using Colebrook-White
    if reynolds < 2000:
        friction_factor = 64 / reynolds  # laminar flow
    else:
        # Colebrook approximation
        rel_roughness = 0.0006 / d  # assuming 0.0006 inches roughness
        friction_factor = (-1.8 * math.log10((rel_roughness/3.7)**1.11 + 6.9/reynolds))**(-2)
    
    # Determine flow regime
    if reynolds < 2000:
        flow_regime = "Laminar"
    elif reynolds < 4000:
        flow_regime = "Transitional"
    else:
        flow_regime = "Turbulent"
    
    # Return calculation results
    return {
        "inlet_pressure": inlet_pressure,
        "outlet_pressure": outlet_pressure,
        "pressure_drop": pressure_drop,
        "flow_velocity": velocity,
        "reynolds_number": reynolds,
        "friction_factor": friction_factor,
        "flow_regime": flow_regime,
        "z_factor": z_factor,
        "is_valid": is_valid,
        "max_flow": max_flow
    }


def calculate_max_flow_rate(
    diameter: float,     # inside diameter, inches
    length: float,       # pipe length, ft
    inlet_pressure: float,  # inlet pressure, psia
    gas_gravity: float,  # gas specific gravity (air=1)
    temperature: float,  # average gas temperature, °F
    z_factor: Optional[float] = None,  # gas compressibility factor
    efficiency: float = 1.0,  # pipe efficiency factor (0.5-1.0)
) -> float:
    """
    Calculate maximum gas flow rate using the Weymouth equation.
    
    Args:
        diameter: Pipe inside diameter in inches
        length: Pipe length in feet
        inlet_pressure: Inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)
        
    Returns:
        Maximum flow rate in Mscf/d
    """
    # Convert units as needed
    d = diameter  # inches
    length_miles = length / 5280  # convert feet to miles
    t_avg = temperature + 460  # convert °F to °R
    
    # Calculate z-factor if not provided
    if z_factor is None:
        # Simple z-factor correlation
        p_avg = inlet_pressure * 0.67  # for max flow, p2 is lower relative to p1
        p_pr = p_avg / (709 - 58 * gas_gravity)
        t_pr = t_avg / (170 + 314 * gas_gravity)
        z_factor = 1.0 - 0.06 * p_pr / t_pr
    
    # Weymouth constant
    C = 433.5
    
    # Minimum allowable outlet pressure (could be adjusted based on requirements)
    p2_min = max(14.7, inlet_pressure * 0.1)  # 10% of inlet or atmospheric
    
    # Calculate maximum flow using Weymouth equation
    # Q = (C * E * d^2.667 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5)
    max_flow = (C * efficiency * d**2.667 * math.sqrt(inlet_pressure**2 - p2_min**2)) / \
               (math.sqrt(t_avg * gas_gravity * length_miles))
    
    return max_flow


def calculate_diameter_weymouth(
    gas_rate: float,     # gas flow rate, Mscf/d
    length: float,       # pipe length, ft
    inlet_pressure: float,  # inlet pressure, psia
    outlet_pressure: float,  # outlet pressure, psia
    gas_gravity: float,  # gas specific gravity (air=1)
    temperature: float,  # average gas temperature, °F
    z_factor: Optional[float] = None,  # gas compressibility factor
    efficiency: float = 1.0,  # pipe efficiency factor (0.5-1.0)
) -> float:
    """
    Calculate required pipe diameter using the Weymouth equation.
    
    Args:
        gas_rate: Gas flow rate in Mscf/d
        length: Pipe length in feet
        inlet_pressure: Inlet pressure in psia
        outlet_pressure: Outlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)
        
    Returns:
        Required pipe diameter in inches
    """
    # Convert units as needed
    length_miles = length / 5280  # convert feet to miles
    t_avg = temperature + 460  # convert °F to °R
    
    # Calculate z-factor if not provided
    if z_factor is None:
        # Simple z-factor correlation
        p_avg = (inlet_pressure + outlet_pressure) / 2
        p_pr = p_avg / (709 - 58 * gas_gravity)
        t_pr = t_avg / (170 + 314 * gas_gravity)
        z_factor = 1.0 - 0.06 * p_pr / t_pr
    
    # Weymouth constant
    C = 433.5
    
    # Calculate diameter using Weymouth equation
    # Q = (C * E * d^2.667 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5)
    # Rearranged for d:
    # d = [(Q * T_avg^0.5 * G^0.5 * L^0.5) / (C * E * (p1^2 - p2^2)^0.5)]^(1/2.667)
    
    term = (gas_rate * math.sqrt(t_avg * gas_gravity * length_miles)) / \
           (C * efficiency * math.sqrt(inlet_pressure**2 - outlet_pressure**2))
    
    diameter = term ** (1/2.667)
    
    return diameter