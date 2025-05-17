# app/services/hydraulics/extensions/pipeline.py

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple

# Set up logging
logger = logging.getLogger(__name__)

def calculate_elevation_effect(length: float, inclination: float, fluid_density: float) -> float:
    """
    Calculate pressure change due to elevation change
    
    Args:
        length (float): Length of segment in feet
        inclination (float): Angle from horizontal in degrees
        fluid_density (float): Fluid density in lb/ft³
        
    Returns:
        float: Pressure change due to elevation in psi
    """
    # Convert inclination to height change
    height_change = length * np.sin(np.radians(inclination))
    
    # Calculate hydrostatic pressure change (ρgh)
    # Convert from lb/ft³ × ft to psi
    pressure_change = fluid_density * height_change / 144
    
    logger.debug(f"Elevation effect: length={length}ft, inclination={inclination}°, height_change={height_change}ft, pressure_change={pressure_change}psi")
    
    return pressure_change

def calculate_fitting_losses(fittings: Dict[str, int], diameter: float, flowrate: float) -> float:
    """
    Calculate pressure losses from pipeline fittings
    
    Args:
        fittings (dict): Dictionary of fitting types and quantities, e.g. {"elbow_90": 3, "tee_flow_through": 2}
        diameter (float): Pipe diameter in inches
        flowrate (float): Flow rate in STB/d
        
    Returns:
        float: Additional pressure drop in psi
    """
    # K-values for common fittings (resistance coefficients)
    k_values = {
        'elbow_90': 0.75,
        'elbow_45': 0.4,
        'tee_flow_through': 0.4,
        'tee_branch_flow': 1.0,
        'gate_valve_open': 0.2,
        'gate_valve_half_open': 5.6,
        'check_valve': 2.5,
        'globe_valve': 10.0,
        'sudden_expansion': 1.0,
        'sudden_contraction': 0.5,
        'entrance': 0.5,
        'exit': 1.0
    }
    
    # Convert flowrate from STB/d to ft³/s for calculation
    flow_ft3_sec = flowrate * 5.615 / 86400
    
    # Calculate pipe area in ft²
    area_ft2 = np.pi * (diameter / 24) ** 2
    
    # Calculate velocity in ft/s
    velocity = flow_ft3_sec / area_ft2
    
    # Calculate total K-value
    total_k = 0
    for fitting_type, quantity in fittings.items():
        if fitting_type in k_values:
            total_k += k_values[fitting_type] * quantity
    
    # Calculate pressure drop using K-value method (ΔP = K * ρ * v² / 2g)
    # Assuming average oil density of 55 lb/ft³
    fluid_density = 55  # lb/ft³
    gravity = 32.2  # ft/s²
    
    pressure_drop = total_k * fluid_density * velocity ** 2 / (2 * gravity)
    
    # Convert from lb/ft² to psi
    pressure_drop = pressure_drop / 144
    
    logger.debug(f"Fitting losses: total_k={total_k}, velocity={velocity}ft/s, pressure_drop={pressure_drop}psi")
    
    return pressure_drop

def adapt_hydraulics_input_for_pipeline(pipeline_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapt pipeline-specific input to the format expected by hydraulics engine
    
    Args:
        pipeline_input: Pipeline hydraulics input
        
    Returns:
        dict: Adapted input for hydraulics calculation functions
    """
    # Extract key values from pipeline input
    segment = pipeline_input.get("segment", {})
    fluid = pipeline_input.get("fluid", {})
    
    # Get fluid properties
    fluid_type = fluid.get("type", "oil")
    oil_api = fluid.get("oil_api", 35)
    water_cut = fluid.get("water_cut", 0)
    gor = fluid.get("gor", 0)
    gas_gravity = fluid.get("gas_gravity", 0.65)
    temperature = fluid.get("temperature", 150)
    bubble_point = fluid.get("bubble_point", 2000)
    
    # Calculate flowrates for oil, water and gas
    total_liquid_rate = segment.get("flowrate", 100)
    oil_rate = total_liquid_rate * (1 - water_cut)
    water_rate = total_liquid_rate * water_cut
    gas_rate = (oil_rate * gor) / 1000 if gor > 0 else 0
    
    # Convert pipeline angle (from horizontal) to wellbore deviation (from vertical)
    # Pipeline: 0° = horizontal, 90° = vertical up, -90° = vertical down
    # Wellbore: 0° = vertical, 90° = horizontal
    pipeline_angle = segment.get("inclination", 0)
    wellbore_deviation = 90 - pipeline_angle if pipeline_angle >= 0 else 90 + abs(pipeline_angle)
    
    # Create hydraulics input in the format expected by hydraulics engine
    hydraulics_input = {
        "fluid_properties": {
            "oil_rate": oil_rate,
            "water_rate": water_rate,
            "gas_rate": gas_rate,
            "oil_gravity": oil_api,
            "water_gravity": fluid.get("water_gravity", 1.05),
            "gas_gravity": gas_gravity,
            "bubble_point": bubble_point,
            "temperature_gradient": 0.0,  # Assume constant temperature for pipeline
            "surface_temperature": temperature
        },
        "wellbore_geometry": {
            "depth": segment.get("length", 1000),
            "deviation": wellbore_deviation,
            "tubing_id": segment.get("diameter", 4),
            "roughness": segment.get("roughness", 0.0006),
            "depth_steps": 100  # Default number of calculation steps
        },
        "method": pipeline_input.get("correlation", "beggs-brill"),
        "surface_pressure": segment.get("inlet_pressure", 500),
        "bhp_mode": "calculate"
    }
    
    # If outlet pressure is specified, set target BHP mode
    if segment.get("outlet_pressure") is not None:
        hydraulics_input["bhp_mode"] = "target"
        hydraulics_input["target_bhp"] = segment.get("outlet_pressure")
    
    logger.debug(f"Adapted hydraulics input for pipeline: {hydraulics_input}")
    return hydraulics_input

def adapt_hydraulics_output_for_pipeline(hydraulics_result: Dict[str, Any], pipeline_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapt hydraulics calculation result to pipeline-specific format
    
    Args:
        hydraulics_result: Result from hydraulics calculation
        pipeline_input: Original pipeline input
        
    Returns:
        dict: Adapted result in pipeline format
    """
    # Extract segment data from input
    segment = pipeline_input.get("segment", {})
    segment_id = segment.get("id", "unknown")
    diameter = segment.get("diameter", 4)
    length = segment.get("length", 1000)
    flowrate = segment.get("flowrate", 100)
    
    # Extract primary pressure values
    inlet_pressure = hydraulics_result.get("surface_pressure", 0)
    bottomhole_pressure = hydraulics_result.get("bottomhole_pressure", 0)
    outlet_pressure = bottomhole_pressure
    pressure_drop = hydraulics_result.get("overall_pressure_drop", inlet_pressure - outlet_pressure)
    
    # Get detailed profile information
    pressure_profile = hydraulics_result.get("pressure_profile", [])
    
    # Extract flow regime and holdup information
    flow_patterns = hydraulics_result.get("flow_patterns", [])
    predominant_flow_regime = None
    if flow_patterns:
        # Find the most common flow pattern
        from collections import Counter
        pattern_counter = Counter([p.flow_pattern for p in flow_patterns if hasattr(p, 'flow_pattern')])
        if pattern_counter:
            predominant_flow_regime = pattern_counter.most_common(1)[0][0]
    
    # Calculate mixture velocity (using the first point from profile if available)
    if pressure_profile and hasattr(pressure_profile[0], 'mixture_velocity'):
        mixture_velocity = pressure_profile[0].mixture_velocity
    else:
        # Estimate velocity if not provided
        area = np.pi * (diameter / 24) ** 2  # Convert to feet
        flowrate_ft3_sec = flowrate * 5.615 / 86400  # Convert STB/d to ft³/s
        mixture_velocity = flowrate_ft3_sec / area if area > 0 else 0
    
    # Get friction factor, Reynolds number and pressure components
    friction_factor = None
    reynolds_number = None
    elevation_pressure_drop = None
    friction_pressure_drop = None
    
    if pressure_profile:
        # Average values from the profile
        valid_points = [p for p in pressure_profile if hasattr(p, 'friction_factor') and p.friction_factor is not None]
        if valid_points:
            friction_factor = sum(p.friction_factor for p in valid_points) / len(valid_points)
        
        valid_points = [p for p in pressure_profile if hasattr(p, 'reynolds_number') and p.reynolds_number is not None]
        if valid_points:
            reynolds_number = sum(p.reynolds_number for p in valid_points) / len(valid_points)
        
        # Calculate pressure drop components
        elevation_drop_pct = hydraulics_result.get("elevation_drop_percentage", 0)
        friction_drop_pct = hydraulics_result.get("friction_drop_percentage", 0)
        
        if pressure_drop > 0:
            elevation_pressure_drop = pressure_drop * elevation_drop_pct / 100.0
            friction_pressure_drop = pressure_drop * friction_drop_pct / 100.0
    
    # Create pipeline result
    pipeline_result = {
        "segment_id": segment_id,
        "inlet_pressure": inlet_pressure,
        "outlet_pressure": outlet_pressure,
        "pressure_drop": pressure_drop,
        "flow_velocity": mixture_velocity,
        "reynolds_number": reynolds_number,
        "friction_factor": friction_factor,
        "flow_regime": predominant_flow_regime,
        "hold_up": None,  # Would need to calculate average from profile
        "elevation_pressure_drop": elevation_pressure_drop,
        "friction_pressure_drop": friction_pressure_drop,
        "correlation": pipeline_input.get("correlation", "beggs-brill"),
        "distance_points": [p.depth for p in pressure_profile] if pressure_profile else None,
        "pressure_points": [p.pressure for p in pressure_profile] if pressure_profile else None
    }
    
    logger.debug(f"Adapted hydraulics output for pipeline: pressure_drop={pressure_drop}psi, velocity={mixture_velocity}ft/s")
    return pipeline_result