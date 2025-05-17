# Standard imports
import numpy as np
import math
from typing import List, Dict, Any, Tuple, Optional

# Schema imports
from app.schemas.hydraulics import (
    HydraulicsInput, 
    HydraulicsResult, 
    PressurePoint, 
    FlowPatternEnum, 
    FlowPatternResult
)

# Utility imports
from ..utils import calculate_fluid_properties

# Constants
PI = math.pi

def calculate_mukherjee_brill(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Mukherjee-Brill correlation
    Specialized for directional (deviated) wells
    """
    # Extract input data
    fluid = data.fluid_properties
    wellbore = data.wellbore_geometry
    surface_pressure = data.surface_pressure
    
    # Calculate depth points
    depth_steps = wellbore.depth_steps
    depth_points = np.linspace(0, wellbore.depth, depth_steps)
    
    # Initialize arrays for results
    pressures = np.zeros(depth_steps)
    temperatures = np.zeros(depth_steps)
    holdups = np.zeros(depth_steps)
    flow_patterns = [None] * depth_steps
    mixture_densities = np.zeros(depth_steps)
    mixture_velocities = np.zeros(depth_steps)
    friction_factors = np.zeros(depth_steps)
    reynolds_numbers = np.zeros(depth_steps)
    dpdz_elevation = np.zeros(depth_steps)
    dpdz_friction = np.zeros(depth_steps)
    dpdz_acceleration = np.zeros(depth_steps)
    dpdz_total = np.zeros(depth_steps)
    
    # Set initial conditions
    pressures[0] = surface_pressure
    temperatures[0] = fluid.surface_temperature
    
    # Calculate temperature profile (linear gradient)
    for i in range(depth_steps):
        temperatures[i] = fluid.surface_temperature + fluid.temperature_gradient * depth_points[i]
    
    # Convert to field units
    g_c = 32.17  # Conversion factor, ft-lbm/lbf-s^2
    g = 32.2     # Acceleration due to gravity, ft/s²
    tubing_diameter = wellbore.tubing_id / 12  # convert to ft
    tubing_area = PI * (tubing_diameter/2)**2
    roughness_rel = wellbore.roughness / (wellbore.tubing_id * 12)  # relative roughness
    
    # Calculation loop - march down the wellbore
    for i in range(depth_steps-1):
        # Current conditions
        p_current = pressures[i]
        t_current = temperatures[i]
        depth_current = depth_points[i]
        
        # Calculate fluid properties at current conditions
        props = calculate_fluid_properties(
            p_current, 
            t_current, 
            {
                "oil_gravity": fluid.oil_gravity,
                "gas_gravity": fluid.gas_gravity,
                "bubble_point": fluid.bubble_point,
                "water_gravity": fluid.water_gravity
            }
        )
        
        # Calculate flow rates in reservoir conditions
        oil_flow_ft3day = fluid.oil_rate * 5.615 * props["oil_fvf"]
        water_flow_ft3day = fluid.water_rate * 5.615 * props["water_fvf"]
        gas_flow_ft3day = fluid.gas_rate * 1000 * props["gas_fvf"]
        
        # Convert to velocity (ft/s)
        v_sl = (oil_flow_ft3day + water_flow_ft3day) / (86400 * tubing_area)  # Superficial liquid velocity
        v_sg = gas_flow_ft3day / (86400 * tubing_area)  # Superficial gas velocity
        v_m = v_sl + v_sg  # Mixture velocity
        
        # Calculate input liquid fraction (no-slip holdup)
        C_L = v_sl / (v_sl + v_sg + 1e-10)
        
        # Calculate liquid and gas densities (lb/ft³)
        oil_density = 62.4 / props["oil_fvf"]
        water_density = 62.4 * fluid.water_gravity / props["water_fvf"]
        gas_density = 0.0764 * fluid.gas_gravity / props["gas_fvf"]
        
        # Calculate weighted liquid properties
        total_liquid_rate = fluid.oil_rate + fluid.water_rate
        liquid_density = (fluid.oil_rate * oil_density + fluid.water_rate * water_density) / total_liquid_rate
        liquid_viscosity = (fluid.oil_rate * props["oil_viscosity"] + fluid.water_rate * props["water_viscosity"]) / total_liquid_rate
        
        # Surface tension (approximate)
        # Oil-gas surface tension decreases with pressure and temperature
        sigma_oil_gas = max(1.0, 30.0 - 0.1 * (t_current - 60) - 0.005 * (p_current - 14.7))  # dynes/cm
        # Water-gas surface tension is typically higher
        sigma_water_gas = max(5.0, 70.0 - 0.15 * (t_current - 60) - 0.01 * (p_current - 14.7))  # dynes/cm
        
        # Weighted surface tension
        if total_liquid_rate > 0:
            oil_fraction = fluid.oil_rate / total_liquid_rate
            water_fraction = fluid.water_rate / total_liquid_rate
            sigma = oil_fraction * sigma_oil_gas + water_fraction * sigma_water_gas
        else:
            sigma = sigma_oil_gas  # Default to oil-gas if no liquid
            
        # Convert surface tension from dynes/cm to lbf/ft
        sigma_lbf_ft = sigma * 6.85e-5
        
        # Flow pattern identification for Mukherjee & Brill
        # Use inclination-aware flow pattern map
        theta = np.radians(wellbore.deviation)
        downward = theta < 0
        
        # Simplified transition criteria for Mukherjee-Brill
        # These are approximations of their original work
        
        # Dimensionless parameters
        N_Fr = v_m**2 / (g * tubing_diameter)  # Froude number
        N_LV = 1.938 * v_sl * ((liquid_density / (g * sigma_lbf_ft))**0.25)  # Liquid velocity number
        
        # Transition velocities - simplified from Mukherjee-Brill
        v_transition_A = 0.5 + 0.1 * np.abs(np.sin(theta)) # Bubble/Slug transition
        v_transition_stratified = 0.3 * np.sqrt(tubing_diameter)  # Stratified transition (for downhill)
        v_transition_C = 8.0 - 3.0 * np.abs(np.sin(theta))  # Slug/Annular transition
        
        # Flow pattern determination
        if v_sg < v_transition_A:
            if v_sl > 0.3:  # Higher liquid velocity favors bubble
                regime = "Bubble/Slug"
                flow_patterns[i] = FlowPatternEnum.BUBBLE
            else:
                regime = "Bubble/Slug"
                flow_patterns[i] = FlowPatternEnum.SLUG
        elif downward and v_sg < v_transition_stratified:
            regime = "Stratified (Downhill)"
            flow_patterns[i] = FlowPatternEnum.STRATIFIED
        elif v_sg < v_transition_C:
            regime = "Slug/Churn"
            flow_patterns[i] = FlowPatternEnum.TRANSITION
        else:
            regime = "Annular"
            flow_patterns[i] = FlowPatternEnum.ANNULAR
        
        # Liquid holdup calculation
        if regime == "Bubble/Slug":
            # In dispersed bubble or slug, start with no-slip holdup
            H_L0 = C_L
            # Apply Palmer correction for uphill flow
            if theta > 0:
                # Slight reduction for uphill (Palmer correction)
                H_L = 0.918 * H_L0
            else:
                H_L = H_L0
        elif regime == "Stratified (Downhill)":
            # Stratified flow (downhill): liquid in bottom, gas on top.
            # Simplified stratified holdup calculation
            # For pure stratified, can use geometric approach
            # But Mukherjee-Brill uses more complex formulas
            # Here's a simplified approach:
            H_L = 0.5 * (1.0 + v_sl / (v_sl + v_sg) - 0.2 * np.sin(-theta))
        elif regime == "Slug/Churn":
            # Slug/Churn: start with no-slip and adjust for inclination
            H_L0 = C_L
            # Inclination correction factor (simplified)
            f_incline = 1.0 - 0.15 * np.abs(np.sin(theta))
            H_L = H_L0 * f_incline
        else:  # Annular
            # Annular-mist: high gas fraction, liquid as film.
            H_L = 0.9 * C_L  # Assume most liquid entrained with gas (slight slip)
        
        # Ensure holdup is within physical limits
        H_L = max(0.01, min(0.99, H_L))
        holdups[i] = H_L
        
        # Mixture properties
        # No-slip mixture density
        rho_ns = C_L * liquid_density + (1 - C_L) * gas_density
        # Slip mixture density
        rho_s = H_L * liquid_density + (1 - H_L) * gas_density
        mixture_densities[i] = rho_s
        
        # No-slip mixture viscosity (simplified)
        mu_ns = C_L * liquid_viscosity + (1 - C_L) * props["gas_viscosity"]
        
        # Friction factor calculation
        if regime in ["Bubble/Slug", "Slug/Churn"]:
            # Use no-slip Moody friction factor (liquid dominated)
            Re_ns = (rho_ns * v_m * tubing_diameter) / (mu_ns + 1e-10)
            reynolds_numbers[i] = Re_ns
            
            if Re_ns > 2100:
                # Turbulent
                f_D = (-1.8 * np.log10(((roughness_rel/3.7)**1.11) + (6.9/Re_ns)))**(-2)
            else:
                # Laminar
                f_D = 64.0 / Re_ns
        elif regime == "Stratified (Downhill)":
            # For stratified, should use separate phase friction factors
            # This is a simplified approach:
            Re_L = (liquid_density * v_sl * tubing_diameter) / (liquid_viscosity + 1e-10)
            Re_G = (gas_density * v_sg * tubing_diameter) / (props["gas_viscosity"] + 1e-10)
            reynolds_numbers[i] = H_L * Re_L + (1 - H_L) * Re_G
            
            # Calculate friction factors for each phase
            if Re_L > 2100:
                f_L = (-1.8 * np.log10(((roughness_rel/3.7)**1.11) + (6.9/Re_L)))**(-2)
            else:
                f_L = 64.0 / Re_L
                
            if Re_G > 2100:
                f_G = (-1.8 * np.log10(((roughness_rel/3.7)**1.11) + (6.9/Re_G)))**(-2)
            else:
                f_G = 64.0 / Re_G
            
            # Combined friction factor (weighted by shear stress areas)
            f_D = f_L * H_L + f_G * (1 - H_L)
        elif regime == "Annular":
            # Annular flow: use friction factor correlation function of holdup ratio
            phi = H_L / (C_L + 1e-10)  # holdup ratio
            f_ns = 0.0  # Base no-slip friction
            
            # No-slip Reynolds number
            Re_ns = (rho_ns * v_m * tubing_diameter) / (mu_ns + 1e-10)
            reynolds_numbers[i] = Re_ns
            
            if Re_ns > 2100:
                # Turbulent
                f_ns = (-1.8 * np.log10(((roughness_rel/3.7)**1.11) + (6.9/Re_ns)))**(-2)
            else:
                # Laminar
                f_ns = 64.0 / Re_ns
            
            # F(phi) = empirically derived function that increases f with holdup ratio
            # This is a simplified model of the Mukherjee-Brill adjustment
            if phi < 1.0:
                F_phi = 1.0  # No adjustment for phi < 1
            else:
                F_phi = phi**0.5  # Increase friction for phi > 1
                
            f_D = f_ns * F_phi
        
        friction_factors[i] = f_D
        
        # Pressure gradient components
        # Hydrostatic component (psi/ft)
        dp_elevation = rho_s * g * np.sin(theta) / (144.0 * g_c)  # psi/ft
        
        # Friction component (psi/ft)
        dp_friction = (f_D * rho_ns * v_m**2) / (2 * g_c * tubing_diameter * 144.0)  # psi/ft
        
        # Acceleration component (psi/ft)
        # Typically small for most conditions
        dp_acceleration = 0.0
        
        # Total pressure gradient (psi/ft)
        dp_total = dp_elevation + dp_friction + dp_acceleration
        
        # Store gradient components
        dpdz_elevation[i] = dp_elevation
        dpdz_friction[i] = dp_friction
        dpdz_acceleration[i] = dp_acceleration
        dpdz_total[i] = dp_total
        
        # Calculate next pressure
        # Using the step size
        dz = depth_points[i+1] - depth_points[i]
        pressures[i+1] = p_current + dp_total * dz
        
        # Store the mixture velocity
        mixture_velocities[i] = v_m
    
    # Create result objects
    pressure_profile = []
    for i in range(depth_steps):
        pressure_profile.append(
            PressurePoint(
                depth=depth_points[i],
                pressure=pressures[i],
                temperature=temperatures[i],
                flow_pattern=flow_patterns[i],
                liquid_holdup=holdups[i],
                mixture_density=mixture_densities[i] if i < len(mixture_densities) else None,
                mixture_velocity=mixture_velocities[i] if i < len(mixture_velocities) else None,
                reynolds_number=reynolds_numbers[i] if i < len(reynolds_numbers) else None,
                friction_factor=friction_factors[i] if i < len(friction_factors) else None,
                dpdz_elevation=dpdz_elevation[i] if i < len(dpdz_elevation) else None,
                dpdz_friction=dpdz_friction[i] if i < len(dpdz_friction) else None,
                dpdz_acceleration=dpdz_acceleration[i] if i < len(dpdz_acceleration) else None,
                dpdz_total=dpdz_total[i] if i < len(dpdz_total) else None
            )
        )
    
    # Calculate overall pressure drop components
    total_elevation = sum(dpdz_elevation) * (wellbore.depth / (depth_steps-1))
    total_friction = sum(dpdz_friction) * (wellbore.depth / (depth_steps-1))
    total_acceleration = sum(dpdz_acceleration) * (wellbore.depth / (depth_steps-1))
    total_drop = total_elevation + total_friction + total_acceleration
    
    # Calculate percentages
    elevation_pct = (total_elevation / total_drop) * 100 if total_drop > 0 else 0
    friction_pct = (total_friction / total_drop) * 100 if total_drop > 0 else 0
    acceleration_pct = (total_acceleration / total_drop) * 100 if total_drop > 0 else 0
    
    # Prepare flow pattern results
    flow_pattern_results = []
    sample_interval = max(1, depth_steps // 20)  # Sample about 20 points
    
    for i in range(0, depth_steps, sample_interval):
        if i < len(mixture_velocities):
            v_m_i = mixture_velocities[i]
        else:
            v_m_i = 0.0
            
        if i < len(holdups):
            h_l_i = holdups[i]
        else:
            h_l_i = 0.0
            
        flow_pattern_results.append(
            FlowPatternResult(
                depth=depth_points[i],
                flow_pattern=flow_patterns[i] or FlowPatternEnum.BUBBLE,
                liquid_holdup=h_l_i,
                mixture_velocity=v_m_i,
                superficial_liquid_velocity=v_sl,
                superficial_gas_velocity=v_sg
            )
        )
    
    # Return results
    return HydraulicsResult(
        method="Mukherjee-Brill",  # Corrected method name
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=elevation_pct,
        friction_drop_percentage=friction_pct,
        acceleration_drop_percentage=acceleration_pct,
        flow_patterns=flow_pattern_results
    )