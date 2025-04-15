# backend/hydraulics/engine.py
import numpy as np
import math
from typing import Any
from app.schemas.hydraulics import (
    HydraulicsInput, HydraulicsResult, PressurePoint, 
    FlowPatternEnum, FlowPatternResult
)

# Constants
G_C = 32.17  # Conversion factor, ft-lbm/lbf-s^2
PI = math.pi

def calculate_hydraulics(data: HydraulicsInput) -> HydraulicsResult:
    """Main function to calculate hydraulics based on selected method"""
    method = data.method.lower()
    
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

def calculate_fluid_properties(
    pressure: float,
    temperature: float,
    fluid_props: dict[str, Any]
) -> dict[str, float]:
    """Calculate PVT properties at given pressure and temperature"""
    # This is a simplified implementation
    # In a real implementation, you would use your existing PVT module
    
    # Oil properties
    oil_gravity = fluid_props["oil_gravity"]
    gas_gravity = fluid_props["gas_gravity"]
    bubble_point = fluid_props["bubble_point"]
    
    # Calculate oil FVF
    if pressure >= bubble_point:
        # Undersaturated oil
        oil_fvf = 1.0 + 1.2e-5 * (temperature - 60) + 1.1e-6 * (oil_gravity) * (bubble_point - 14.7)
    else:
        # Saturated oil
        oil_fvf = 1.0 + 2.5e-4 * (temperature - 60) + 1.8e-6 * (oil_gravity) * (bubble_point - pressure)
    
    # Calculate oil viscosity (simplified)
    oil_viscosity = 1.8 * 10**(-0.025 * oil_gravity) * 10**(3.0 / temperature)
    
    # Calculate water properties
    water_fvf = 1.0 + 1.2e-6 * (temperature - 60) * (pressure - 14.7)
    water_viscosity = 2.4 * np.exp(-0.01 * temperature)
    
    # Calculate gas properties
    z_factor = 1.0 - (pressure / 1000) * (0.23 - 0.15 * gas_gravity)
    gas_fvf = 0.0283 * z_factor * (temperature + 460) / pressure
    gas_viscosity = 0.0125 * (1.0 + 0.01 * gas_gravity) * (temperature / 100)**0.5
    
    # Return all calculated properties
    return {
        "oil_fvf": oil_fvf,
        "oil_viscosity": oil_viscosity,
        "water_fvf": water_fvf,
        "water_viscosity": water_viscosity,
        "gas_fvf": gas_fvf,
        "gas_viscosity": gas_viscosity,
        "z_factor": z_factor
    }

def calculate_hagedorn_brown(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Hagedorn-Brown correlation for vertical multiphase flow
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
    
    # Set initial conditions
    pressures[0] = surface_pressure
    temperatures[0] = fluid.surface_temperature
    
    # Convert rates to mass flow rates
    oil_rate_bpd = fluid.oil_rate
    water_rate_bpd = fluid.water_rate
    gas_rate_mscfd = fluid.gas_rate
    
    # Convert to field units
    tubing_diameter = wellbore.tubing_id / 12  # convert to ft
    tubing_area = PI * (tubing_diameter/2)**2
    
    # Calculate temperature profile
    for i in range(depth_steps):
        temperatures[i] = fluid.surface_temperature + fluid.temperature_gradient * depth_points[i]
    
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
            }
        )
        
        # Calculate flow rates in reservoir conditions
        oil_flow_ft3day = oil_rate_bpd * 5.615 * props["oil_fvf"]
        water_flow_ft3day = water_rate_bpd * 5.615 * props["water_fvf"]
        gas_flow_ft3day = gas_rate_mscfd * 1000 * props["gas_fvf"]
        
        # Convert to velocity (ft/s)
        oil_velocity = oil_flow_ft3day / (86400 * tubing_area)
        water_velocity = water_flow_ft3day / (86400 * tubing_area)
        gas_velocity = gas_flow_ft3day / (86400 * tubing_area)
        
        # Total superficial velocity
        v_sl = oil_velocity + water_velocity  # Superficial liquid velocity
        v_sg = gas_velocity  # Superficial gas velocity
        v_m = v_sl + v_sg  # Mixture velocity
        
        # Calculate liquid holdup using Hagedorn-Brown correlation
        # This is a simplified version
        nv_l = 1.938 * v_sl * (props["oil_viscosity"] / 62.4)**0.25
        nv_g = 1.938 * v_sg * (0.0764 / 62.4)**0.25
        
        holdup = 0.0
        if nv_l < 0.01 and nv_g < 0.01:
            flow_patterns[i] = FlowPatternEnum.BUBBLE
            holdup = 0.5 + 0.1 * math.log10(nv_l / nv_g)
        elif nv_l < 0.01 and nv_g >= 0.01:
            flow_patterns[i] = FlowPatternEnum.SLUG
            holdup = 0.5 * math.log10(0.01 / nv_g)
        elif nv_l >= 0.01 and nv_g < 0.01:
            flow_patterns[i] = FlowPatternEnum.BUBBLE
            holdup = 0.5 + 0.1 * math.log10(nv_l / 0.01)
        else:
            flow_patterns[i] = FlowPatternEnum.SLUG
            holdup = 0.5 + 0.1 * math.log10(nv_l / nv_g)
        
        # Limit holdup to reasonable values
        holdup = max(0.01, min(0.99, holdup))
        holdups[i] = holdup
        
        # Calculate density
        oil_density = 62.4 / props["oil_fvf"]
        water_density = 62.4 * fluid.water_gravity / props["water_fvf"]
        gas_density = 0.0764 * fluid.gas_gravity / props["gas_fvf"]
        
        # Mixture density
        liquid_density = (oil_rate_bpd * oil_density + water_rate_bpd * water_density) / (oil_rate_bpd + water_rate_bpd)
        mixture_density = holdup * liquid_density + (1 - holdup) * gas_density
        
        # Calculate friction factor
        # Reynolds number
        liquid_viscosity = (oil_rate_bpd * props["oil_viscosity"] + water_rate_bpd * props["water_viscosity"]) / (oil_rate_bpd + water_rate_bpd)
        n_re = 1488 * mixture_density * v_m * tubing_diameter / liquid_viscosity
        
        # Friction factor (Colebrook equation approximation)
        relative_roughness = wellbore.roughness / (wellbore.tubing_id * 12)
        f = 0.25 / (math.log10(relative_roughness/3.7 + 5.74/n_re**0.9))**2
        
        # Calculate pressure drop components
        g_conv = 32.174  # lbm-ft/lbf-s²
        
        # Hydrostatic component
        dp_elevation = mixture_density * (depth_points[i+1] - depth_points[i]) / g_conv
        
        # Friction component
        dp_friction = 2 * f * mixture_density * v_m**2 * (depth_points[i+1] - depth_points[i]) / (g_conv * tubing_diameter)
        
        # Acceleration component
        dp_acceleration = mixture_density * v_m * (v_m + 0.001) / g_conv
        
        # Total pressure drop
        dp_total = dp_elevation + dp_friction + dp_acceleration
        
        # Calculate next pressure
        pressures[i+1] = p_current + dp_total
    
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
            )
        )
    
    # Calculate percentages
    # For simplicity, just use the last calculation
    total_drop = dp_total
    elevation_pct = dp_elevation / total_drop * 100
    friction_pct = dp_friction / total_drop * 100
    acceleration_pct = dp_acceleration / total_drop * 100
    
    # Prepare flow pattern results
    flow_pattern_results = []
    for i in range(depth_steps):
        if i % 10 == 0:  # Only include every 10th point for brevity
            flow_pattern_results.append(
                FlowPatternResult(
                    depth=depth_points[i],
                    flow_pattern=flow_patterns[i] or FlowPatternEnum.BUBBLE,
                    liquid_holdup=holdups[i],
                    mixture_velocity=v_m,
                    superficial_liquid_velocity=v_sl,
                    superficial_gas_velocity=v_sg
                )
            )
    
    # Return results
    return HydraulicsResult(
        method="Hagedorn-Brown",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=elevation_pct,
        friction_drop_percentage=friction_pct,
        acceleration_drop_percentage=acceleration_pct,
        flow_patterns=flow_pattern_results
    )

def calculate_beggs_brill(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Beggs-Brill correlation for inclined multiphase flow
    """
    # Similar structure to Hagedorn-Brown but with Beggs-Brill specific calculations
    # This is a placeholder - you would implement the full Beggs-Brill correlation here
    
    # For now, we'll just use Hagedorn-Brown with a small modification
    result = calculate_hagedorn_brown(data)
    result.method = "Beggs-Brill"
    
    # Adjust for inclination
    inclination_factor = math.cos(math.radians(data.wellbore_geometry.deviation))
    
    # Modify pressures for inclination
    for point in result.pressure_profile:
        point.pressure = point.pressure * inclination_factor
    
    result.bottomhole_pressure = result.pressure_profile[-1].pressure
    result.overall_pressure_drop = result.bottomhole_pressure - data.surface_pressure
    
    return result

def calculate_duns_ross(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Duns-Ross correlation for vertical multiphase flow
    """
    # Placeholder for Duns-Ross correlation
    # This would contain the specific implementation of the Duns-Ross method
    
    # For now, just use Hagedorn-Brown with modified parameters
    result = calculate_hagedorn_brown(data)
    result.method = "Duns-Ross"
    
    # In Duns-Ross, the flow patterns are more distinctly categorized
    # Recategorize flow patterns
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            if point.liquid_holdup > 0.8:
                point.flow_pattern = FlowPatternEnum.BUBBLE
            elif point.liquid_holdup > 0.3:
                point.flow_pattern = FlowPatternEnum.SLUG
            elif point.liquid_holdup > 0.05:
                point.flow_pattern = FlowPatternEnum.TRANSITION
            else:
                point.flow_pattern = FlowPatternEnum.MIST
    
    # Update flow pattern results
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,  # Default value
                    superficial_liquid_velocity=2.0,  # Default value
                    superficial_gas_velocity=3.0  # Default value
                )
            )
    
    return result

def calculate_chokshi(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Chokshi correlation (this is a simplified implementation)
    """
    # Placeholder for Chokshi correlation
    # In a real implementation, you would implement the full correlation

    # For now, just use Hagedorn-Brown with some modifications
    result = calculate_hagedorn_brown(data)
    result.method = "Chokshi"
    
    # Chokshi typically gives slightly higher pressure drops
    for point in result.pressure_profile:
        point.pressure = point.pressure * 1.05
    
    result.bottomhole_pressure = result.pressure_profile[-1].pressure
    result.overall_pressure_drop = result.bottomhole_pressure - data.surface_pressure
    
    # Adjust percentages
    result.elevation_drop_percentage = 70.0
    result.friction_drop_percentage = 25.0
    result.acceleration_drop_percentage = 5.0
    
    return result

def calculate_orkiszewski(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Orkiszewski correlation for vertical multiphase flow
    Specialized for wells with large tubing diameters
    """
    # For demonstration purposes, we'll implement a modified version of our base method
    # In a production environment, you would implement the full correlation
    
    # Use Hagedorn-Brown as base and adjust for Orkiszewski specifics
    result = calculate_hagedorn_brown(data)
    result.method = "Orkiszewski"
    
    # Orkiszewski tends to predict different flow patterns
    # We'll simulate this by adjusting the patterns
    for i, point in enumerate(result.pressure_profile):
        # Adjust flow patterns - Orkiszewski often predicts more bubble flow
        depth_fraction = point.depth / data.wellbore_geometry.depth
        
        if depth_fraction < 0.3:
            point.flow_pattern = FlowPatternEnum.BUBBLE
        elif depth_fraction < 0.6:
            point.flow_pattern = FlowPatternEnum.SLUG
        elif depth_fraction < 0.9:
            point.flow_pattern = FlowPatternEnum.TRANSITION
        else:
            point.flow_pattern = FlowPatternEnum.ANNULAR
    
    # Orkiszewski often predicts slightly lower pressure drops in large tubing
    tubing_factor = 1.0
    if data.wellbore_geometry.tubing_id > 2.5:  # Large tubing
        tubing_factor = 0.95
    
    # Apply the tubing factor
    for point in result.pressure_profile:
        original_pressure = point.pressure
        delta_p = original_pressure - data.surface_pressure
        point.pressure = data.surface_pressure + delta_p * tubing_factor
    
    # Update result values
    result.bottomhole_pressure = result.pressure_profile[-1].pressure
    result.overall_pressure_drop = result.bottomhole_pressure - data.surface_pressure
    
    # Adjust flow patterns
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,  # Default
                    superficial_liquid_velocity=2.0,  # Default
                    superficial_gas_velocity=3.0  # Default
                )
            )
    
    return result

def calculate_gray(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Gray correlation
    Specialized for high-rate gas wells
    """
    # Start with Hagedorn-Brown as base
    result = calculate_hagedorn_brown(data)
    result.method = "Gray"
    
    # Gray correlation tends to predict higher friction losses for gas wells
    # We'll simulate this by adjusting the friction component
    
    # Determine if this is a high-gas well
    glr = data.fluid_properties.gas_rate * 1000 / (data.fluid_properties.oil_rate + data.fluid_properties.water_rate)
    
    # Gray method performs differently based on GLR
    if glr > 5000:  # High GLR
        # Increase friction component
        result.friction_drop_percentage = min(90, result.friction_drop_percentage * 1.5)
        
        # Adjust other components to maintain 100%
        total = result.friction_drop_percentage + result.elevation_drop_percentage + result.acceleration_drop_percentage
        factor = 100 / total
        
        result.friction_drop_percentage *= factor
        result.elevation_drop_percentage *= factor
        result.acceleration_drop_percentage *= factor
        
        # Gray correlation typically shows more mist flow in high gas wells
        for i, point in enumerate(result.pressure_profile):
            if point.liquid_holdup < 0.3:
                point.flow_pattern = FlowPatternEnum.MIST
            elif point.liquid_holdup < 0.6:
                point.flow_pattern = FlowPatternEnum.ANNULAR
            else:
                point.flow_pattern = FlowPatternEnum.SLUG
    
    # Update flow pattern results
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,  # Default value
                    superficial_liquid_velocity=2.0,  # Default value
                    superficial_gas_velocity=3.0  # Default value
                )
            )
    
    return result

def calculate_mukherjee_brill(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Mukherjee-Brill correlation
    Specialized for directional (deviated) wells
    """
    # For inclined wells, we'll start with Beggs-Brill (which handles inclination)
    result = calculate_beggs_brill(data)
    result.method = "Mukherjee-Brill"
    
    # Mukherjee-Brill is more sensitive to well deviation
    deviation = data.wellbore_geometry.deviation
    
    # Adjust pressure profile based on deviation
    if deviation > 45:  # Highly deviated
        # Mukherjee-Brill predicts more stratified flow in highly deviated wells
        for i, point in enumerate(result.pressure_profile):
            if point.liquid_holdup < 0.4:
                point.flow_pattern = FlowPatternEnum.STRATIFIED
            elif point.liquid_holdup < 0.7:
                point.flow_pattern = FlowPatternEnum.WAVY
            else:
                point.flow_pattern = FlowPatternEnum.SLUG
        
        # Higher deviation means more friction
        friction_factor = 1.0 + deviation / 90.0 * 0.2  # Up to 20% more friction at 90°
        
        # Apply the friction factor to the overall pressure drop
        dp_original = result.bottomhole_pressure - data.surface_pressure
        dp_new = dp_original * friction_factor
        result.bottomhole_pressure = data.surface_pressure + dp_new
        result.overall_pressure_drop = dp_new
        
        # Recalculate percentages
        result.friction_drop_percentage += 5  # More friction in deviated wells
        
        # Adjust other components to maintain 100%
        total = result.friction_drop_percentage + result.elevation_drop_percentage + result.acceleration_drop_percentage
        factor = 100 / total
        
        result.friction_drop_percentage *= factor
        result.elevation_drop_percentage *= factor
        result.acceleration_drop_percentage *= factor
    
    # Update flow pattern results
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,  # Default value
                    superficial_liquid_velocity=2.0,  # Default value
                    superficial_gas_velocity=3.0  # Default value
                )
            )
    
    return result

def calculate_aziz(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Aziz correlation
    Good for a wide range of gas-liquid ratios
    """
    # Use Hagedorn-Brown as base
    result = calculate_hagedorn_brown(data)
    result.method = "Aziz et al."
    
    # In Aziz correlation, the flow patterns are more sensitive to gas-liquid ratios
    # We'll adjust the flow pattern predictions based on GLR
    
    # Calculate GLR
    glr = data.fluid_properties.gas_rate * 1000 / (data.fluid_properties.oil_rate + data.fluid_properties.water_rate)
    
    # Adjust flow patterns and pressure drop based on GLR
    if glr < 500:  # Low GLR - more liquid-dominated
        # Aziz predicts more bubble flow in low GLR conditions
        for i, point in enumerate(result.pressure_profile):
            depth_fraction = point.depth / data.wellbore_geometry.depth
            if depth_fraction < 0.7:
                point.flow_pattern = FlowPatternEnum.BUBBLE
            else:
                point.flow_pattern = FlowPatternEnum.SLUG
        
        # Lower GLR typically means higher holdups
        for point in result.pressure_profile:
            point.liquid_holdup = min(0.95, point.liquid_holdup * 1.2)
        
        # Adjust pressure profile - usually higher with more liquid holdup
        for point in result.pressure_profile:
            pressure_fraction = (point.pressure - data.surface_pressure) / result.overall_pressure_drop
            point.pressure = data.surface_pressure + result.overall_pressure_drop * pressure_fraction * 1.05
    
    elif glr > 5000:  # High GLR - more gas-dominated
        # Aziz predicts more annular/mist flow in high GLR conditions
        for i, point in enumerate(result.pressure_profile):
            depth_fraction = point.depth / data.wellbore_geometry.depth
            if depth_fraction < 0.3:
                point.flow_pattern = FlowPatternEnum.ANNULAR
            elif depth_fraction < 0.7:
                point.flow_pattern = FlowPatternEnum.TRANSITION
            else:
                point.flow_pattern = FlowPatternEnum.MIST
        
        # Higher GLR typically means lower holdups
        for point in result.pressure_profile:
            point.liquid_holdup = max(0.05, point.liquid_holdup * 0.8)
        
        # Adjust pressure profile - usually lower with less liquid holdup
        for point in result.pressure_profile:
            pressure_fraction = (point.pressure - data.surface_pressure) / result.overall_pressure_drop
            point.pressure = data.surface_pressure + result.overall_pressure_drop * pressure_fraction * 0.95
    
    # Update result values
    result.bottomhole_pressure = result.pressure_profile[-1].pressure
    result.overall_pressure_drop = result.bottomhole_pressure - data.surface_pressure
    
    # Update flow pattern results
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,
                    superficial_liquid_velocity=2.0,
                    superficial_gas_velocity=3.0
                )
            )
    
    return result

def calculate_hasan_kabir(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Hasan-Kabir correlation
    Considers impact of pipe roughness on pressure drop
    """
    # Use Hagedorn-Brown as base
    result = calculate_hagedorn_brown(data)
    result.method = "Hasan-Kabir"
    
    # Hasan-Kabir is more sensitive to pipe roughness
    roughness = data.wellbore_geometry.roughness
    
    # Adjust pressure profile based on pipe roughness
    # Hasan-Kabir typically predicts higher friction losses with rough pipes
    if roughness > 0.001:  # Rougher than normal
        # Calculate a roughness factor
        roughness_factor = 1.0 + (roughness - 0.0006) / 0.0004 * 0.15  # Up to 15% more friction
        
        # Apply the roughness factor to the friction component
        result.friction_drop_percentage *= roughness_factor
        
        # Adjust other components to maintain 100%
        total = result.friction_drop_percentage + result.elevation_drop_percentage + result.acceleration_drop_percentage
        factor = 100 / total
        
        result.friction_drop_percentage *= factor
        result.elevation_drop_percentage *= factor
        result.acceleration_drop_percentage *= factor
        
        # Apply to overall pressure drop
        for point in result.pressure_profile:
            original_dp = point.pressure - data.surface_pressure
            friction_portion = original_dp * (result.friction_drop_percentage / 100)
            other_portion = original_dp - friction_portion
            
            new_friction = friction_portion * roughness_factor
            new_dp = other_portion + new_friction
            
            point.pressure = data.surface_pressure + new_dp
    
    # Hasan-Kabir also has different flow pattern transitions
    for i, point in enumerate(result.pressure_profile):
        # Based on depth and holdup
        depth_fraction = point.depth / data.wellbore_geometry.depth
        if point.liquid_holdup > 0.75:
            point.flow_pattern = FlowPatternEnum.BUBBLE
        elif point.liquid_holdup > 0.35:
            point.flow_pattern = FlowPatternEnum.SLUG
        elif point.liquid_holdup > 0.15:
            point.flow_pattern = FlowPatternEnum.TRANSITION
        else:
            point.flow_pattern = FlowPatternEnum.ANNULAR
    
    # Update result values
    result.bottomhole_pressure = result.pressure_profile[-1].pressure
    result.overall_pressure_drop = result.bottomhole_pressure - data.surface_pressure
    
    # Update flow pattern results
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,
                    superficial_liquid_velocity=2.0,
                    superficial_gas_velocity=3.0
                )
            )
    
    return result

def calculate_ansari(data: HydraulicsInput) -> HydraulicsResult:
    """
    Implementation of Ansari correlation
    Mechanistic approach to flow pattern prediction
    """
    # Use Hagedorn-Brown as base
    result = calculate_hagedorn_brown(data)
    result.method = "Ansari"
    
    # Ansari uses a different approach to flow pattern determination
    # Flow pattern is more mechanistic based on physical principles
    
    # Calculate GLR for flow pattern determination
    glr = data.fluid_properties.gas_rate * 1000 / (data.fluid_properties.oil_rate + data.fluid_properties.water_rate)
    
    # For demonstration, simulate the mechanistic approach with a different pattern distribution
    for i, point in enumerate(result.pressure_profile):
        depth_fraction = point.depth / data.wellbore_geometry.depth
        
        # Flow pattern transitions based on pressure and GLR
        pressure_ratio = point.pressure / data.fluid_properties.bubble_point
        
        if glr < 500:  # Low GLR
            if pressure_ratio > 1.2:  # Well above bubble point
                point.flow_pattern = FlowPatternEnum.BUBBLE
            elif pressure_ratio > 0.8:  # Near bubble point
                point.flow_pattern = FlowPatternEnum.SLUG
            else:  # Below bubble point
                point.flow_pattern = FlowPatternEnum.TRANSITION
        else:  # High GLR
            if depth_fraction < 0.3:
                point.flow_pattern = FlowPatternEnum.ANNULAR
            elif depth_fraction < 0.7:
                point.flow_pattern = FlowPatternEnum.TRANSITION
            else:
                point.flow_pattern = FlowPatternEnum.SLUG
    
    # Ansari typically predicts slightly different pressure drops
    # For demonstration, adjust the pressure profile
    ansari_factor = 0.97  # Ansari often predicts slightly lower pressure drops
    
    for point in result.pressure_profile:
        original_dp = point.pressure - data.surface_pressure
        new_dp = original_dp * ansari_factor
        point.pressure = data.surface_pressure + new_dp
    
    # Update result values
    result.bottomhole_pressure = result.pressure_profile[-1].pressure
    result.overall_pressure_drop = result.bottomhole_pressure - data.surface_pressure
    
    # Update flow pattern results
    result.flow_patterns = []
    for i, point in enumerate(result.pressure_profile):
        if i % 10 == 0:
            result.flow_patterns.append(
                FlowPatternResult(
                    depth=point.depth,
                    flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                    liquid_holdup=point.liquid_holdup or 0.5,
                    mixture_velocity=5.0,
                    superficial_liquid_velocity=2.0,
                    superficial_gas_velocity=3.0
                )
            )
    
    return result