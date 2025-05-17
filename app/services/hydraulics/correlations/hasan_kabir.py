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
def calculate_hasan_kabir(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Hasan-Kabir correlation for multiphase flow
    with consideration of pipe roughness effects
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
        
        # Hasan-Kabir flow pattern identification
        # Use their criteria for boundaries based on superficial velocities
        theta = np.radians(wellbore.deviation)
        
        # Boundary equations (simplified from Hasan-Kabir)
        # Boundary A (bubbly to slug/churn)
        boundary_A = 0.429 * v_sl + 0.357 * v_sl * np.abs(np.sin(theta))
        
        # Boundary C (slug to dispersed bubble) - simplified
        boundary_C = 1.083 * v_sl + 0.52 * np.sqrt(g * (liquid_density - gas_density) / gas_density)
        
        # Flow pattern determination
        if v_sg < boundary_A:
            if v_sl < 1.0:  # Low liquid rate
                regime = "Bubbly"
                flow_patterns[i] = FlowPatternEnum.BUBBLE
            else:  # Higher liquid rate
                regime = "Slug/Churn"
                flow_patterns[i] = FlowPatternEnum.SLUG
        elif v_sg < boundary_C:
            regime = "Dispersed Bubble"
            flow_patterns[i] = FlowPatternEnum.BUBBLE
        else:
            regime = "Annular"
            flow_patterns[i] = FlowPatternEnum.ANNULAR
            
        # Liquid holdup based on regime
        if regime == "Bubbly":
            # Bubbly flow: discrete bubbles, continuous liquid
            # Hasan-Kabir uses drift-flux with their coefficients
            C0 = 1.15  # Distribution parameter
            V_d = 0.0   # Small bubbles assumed carried with liquid
            alpha = (C0 * v_sg) / (v_m + 1e-9)
            alpha = min(max(alpha, 0.0), 0.95)
            H_L = 1.0 - alpha
        elif regime == "Slug/Churn":
            # Slug or churn flow: larger gas pockets
            # Use drift velocity for Taylor bubbles
            C0 = 1.2
            # Simplified form of Hasan-Kabir's drift velocity
            V_d = 1.53 * ((g * (liquid_density - gas_density) * sigma_lbf_ft**2) / (liquid_density**2))**0.25
            alpha = (C0 * v_sg + V_d) / (v_m + 1e-9)
            alpha = min(max(alpha, 0.0), 0.95)
            H_L = 1.0 - alpha
        elif regime == "Dispersed Bubble":
            # Dispersed bubble: high gas fraction, gas pockets broken up
            C0 = 1.0
            V_d = 0.0
            alpha = C0 * v_sg / (v_m + 1e-9)
            alpha = min(max(alpha, 0.0), 0.9)
            H_L = 1.0 - alpha
        else:  # Annular
            # Annular: gas core, liquid film
            H_L = 0.9 * C_L  # Slight slip
            
        # Ensure holdup is within physical limits
        H_L = max(0.01, min(0.99, H_L))
        holdups[i] = H_L
        
        # Mixture properties
        # In Hasan-Kabir, mixture density is calculated based on in-situ volume fractions
        rho_m = H_L * liquid_density + (1.0 - H_L) * gas_density
        mixture_densities[i] = rho_m
        
        # Approximate mixture viscosity
        mu_m = H_L * liquid_viscosity + (1.0 - H_L) * props["gas_viscosity"]
        
        # Reynolds number using mixture properties
        Re_m = (rho_m * v_m * tubing_diameter) / (mu_m + 1e-10)
        reynolds_numbers[i] = Re_m
        
        # Hasan-Kabir is especially concerned with pipe roughness effects
        # Adjust effective roughness based on flow regime and actual roughness
        if roughness_rel > 0.001:  # Rougher than normal
            # Calculate roughness factor based on actual pipe roughness
            roughness_factor = 1.0 + (roughness_rel - 0.0006) / 0.0004
            effective_roughness = roughness_rel * roughness_factor
        else:
            effective_roughness = roughness_rel
            
        # Further adjust based on flow regime
        if regime in ["Bubbly", "Dispersed Bubble"]:
            # Liquid continuous phase - less sensitive to roughness
            effective_roughness *= 0.9
        elif regime == "Annular":
            # Gas continuous with liquid film - more sensitive
            effective_roughness *= 1.2
            
        # Friction factor calculation
        if Re_m > 2100:
            # Turbulent flow
            f_D = (-1.8 * np.log10(((effective_roughness/3.7)**1.11) + (6.9/Re_m)))**(-2)
        else:
            # Laminar flow
            f_D = 64.0 / Re_m
            
        friction_factors[i] = f_D
        
        # Pressure gradient components
        # Hydrostatic component (psi/ft)
        dp_elevation = rho_m * g * np.cos(np.radians(wellbore.deviation)) / (144.0 * g_c)
        
        # Friction component (psi/ft)
        dp_friction = f_D * (rho_m * v_m**2) / (2.0 * g_c * tubing_diameter * 144.0)
        
        # Acceleration component - typically small
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
        method="Hasan-Kabir",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=elevation_pct,
        friction_drop_percentage=friction_pct,
        acceleration_drop_percentage=acceleration_pct,
        flow_patterns=flow_pattern_results
    )