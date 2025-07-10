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

def calculate_beggs_brill(data: HydraulicsInput) -> HydraulicsResult:
    """
    Pure implementation of the Beggs & Brill (1973) multiphase flow correlation.
    This version excludes acceleration pressure drop and uses the original 
    flow regime maps, liquid holdup, and inclination correction as defined by Beggs & Brill.
    """
    # Extract input data
    fluid = data.fluid_properties
    wellbore = data.wellbore_geometry
    surface_pressure = data.surface_pressure
    survey_data = data.survey_data

    # Determine total depth and segment information
    if survey_data and len(survey_data) > 1:
        # Sort survey data by measured depth to ensure correct order
        survey_points = sorted(survey_data, key=lambda p: p.md)
        total_depth = survey_points[-1].md
        segments = []
        for i in range(len(survey_points) - 1):
            start_point = survey_points[i]
            end_point = survey_points[i+1]
            segment_length = end_point.md - start_point.md
            # Use the inclination of the start of the segment for the entire segment
            inclination_rad = math.radians(start_point.inclination)
            segments.append((start_point.md, end_point.md, segment_length, inclination_rad))
    else:
        # Fallback to old method if no survey data is available
        total_depth = wellbore.pipe_segments[-1].end_depth
        segment_length = total_depth / wellbore.depth_steps
        inclination_rad = math.radians(wellbore.deviation)
        segments = [(i * segment_length, (i + 1) * segment_length, segment_length, inclination_rad) for i in range(wellbore.depth_steps)]
    # Initialize results list and initial conditions
    pressure_profile = []
    current_p = surface_pressure
    current_md = 0.0

    # Add surface point to the profile
    surface_t = fluid.surface_temperature
    pressure_profile.append(PressurePoint(
        depth=current_md,
        pressure=current_p,
        temperature=surface_t
    ))

    # Unit conversion constants
    g_c = 32.17    # ft·lbm/(lbf·s^2), unit conversion factor
    g = 32.2       # ft/s^2, gravitational acceleration

    # Stepwise calculation down the wellbore for each segment
    for start_md, end_md, segment_length, inclination_rad in segments:
        # Find the correct pipe segment for the current depth
        current_pipe_segment = None
        for pipe_seg in wellbore.pipe_segments:
            # Check if the start of the calculation segment falls within this pipe segment
            if pipe_seg.start_depth <= start_md < pipe_seg.end_depth:
                current_pipe_segment = pipe_seg
                break
        
        if not current_pipe_segment:
            # If no specific segment is found (e.g., for the very last point at total_depth),
            # use the last available pipe segment.
            current_pipe_segment = wellbore.pipe_segments[-1]

        # Calculate geometry for the current segment
        tubing_id_in = current_pipe_segment.diameter
        tubing_diameter = tubing_id_in / 12.0  # convert tubing ID from inches to ft
        tubing_area = math.pi * (tubing_diameter / 2.0) ** 2
        roughness_rel = wellbore.roughness / tubing_id_in  # relative roughness (unitless)

        # Properties are calculated at the start of the segment
        p = current_p
        T = fluid.surface_temperature + fluid.temperature_gradient * start_md

        # Calculate fluid PVT properties at current pressure/temperature
        props = calculate_fluid_properties(
            p, T, {
                "oil_gravity": fluid.oil_gravity,
                "gas_gravity": fluid.gas_gravity,
                "bubble_point": fluid.bubble_point,
                "water_gravity": fluid.water_gravity
            }
        )

        # Convert production rates to volumetric flow (ft³/day) at current conditions
        oil_flow_ft3day = fluid.oil_rate * 5.615 * props["oil_fvf"]     # STB/d to ft³/d for oil
        water_flow_ft3day = fluid.water_rate * 5.615 * props["water_fvf"]  # STB/d to ft³/d for water
        gas_flow_ft3day = fluid.gas_rate * 1000.0 * props["gas_fvf"]    # Mscf/d to scf/d, then to ft³/d for gas

        # Compute superficial velocities (ft/s)
        v_sl = (oil_flow_ft3day + water_flow_ft3day) / (86400.0 * tubing_area)  # superficial liquid velocity
        v_sg = gas_flow_ft3day / (86400.0 * tubing_area)                        # superficial gas velocity
        v_m = v_sl + v_sg  # mixture velocity

        # No-slip liquid content (input liquid fraction C_L)
        C_L = 0.0
        if (v_sl + v_sg) > 0:
            C_L = v_sl / (v_sl + v_sg)

        # Fluid densities at current conditions (lbm/ft³)
        oil_density = 62.4 / props["oil_fvf"]  # oil FVF in bbl/STB, 62.4 lbm/ft³ is water density at STP
        water_density = 62.4 * fluid.water_gravity / props["water_fvf"]
        gas_density = 0.0764 * fluid.gas_gravity / props["gas_fvf"]     # gas FVF in ft³/scf, 0.0764 lbm/ft³ is air density at STP

        # Effective liquid phase properties (oil + water mixture)
        total_liquid_rate = fluid.oil_rate + fluid.water_rate  # (STB/d)
        if total_liquid_rate > 0:
            # Weighted average by stock-tank flow rates (could also use volume fractions)
            liquid_density = (fluid.oil_rate * oil_density + fluid.water_rate * water_density) / total_liquid_rate
            liquid_viscosity = (fluid.oil_rate * props["oil_viscosity"] + fluid.water_rate * props["water_viscosity"]) / total_liquid_rate
        else:
            # No liquid case
            liquid_density = water_density  # default to water properties if no oil (this will not be used if no liquid)
            liquid_viscosity = props.get("water_viscosity", 1.0)  # fallback

        # Gas viscosity (from PVT props)
        gas_viscosity = props["gas_viscosity"]

        # Approximate surface tension between liquid and gas (dynes/cm)
        # Using a simplified correlation: oil-gas and water-gas values decreasing with T and P
        sigma_oil_gas = max(1.0, 30.0 - 0.1 * (T - 60.0) - 0.005 * (p - 14.7))
        sigma_water_gas = max(5.0, 70.0 - 0.15 * (T - 60.0) - 0.01 * (p - 14.7))
        if total_liquid_rate > 0:
            oil_frac = fluid.oil_rate / total_liquid_rate
            water_frac = fluid.water_rate / total_liquid_rate
            sigma = oil_frac * sigma_oil_gas + water_frac * sigma_water_gas
        else:
            sigma = sigma_oil_gas

        # --- Beggs & Brill Correlation Calculations ---

        # The `inclination_rad` from the segment is the angle from the vertical.
        # Beggs & Brill angle `theta` is from the horizontal.
        # For upward flow, theta = 90 - inclination.
        theta_rad = (math.pi / 2.0) - inclination_rad

        # 1. Dimensionless numbers for flow regime determination
        N_Fr = v_m**2 / (g * tubing_diameter)  # mixture Froude number
        N_LV = 1.938 * v_sl * ((liquid_density / (g * sigma)) ** 0.25)  # liquid velocity number (dimensionless)

        # 2. Flow pattern map boundaries (L1, L2, L3, L4 from Beggs & Brill)
        L1 = 316.0 * (C_L ** 0.302)
        L2 = 0.0009252 * (C_L ** -2.4684)
        L3 = 0.10 * (C_L ** -1.4516)
        L4 = 0.50 * (C_L ** -6.738)

        # 3. Determine flow regime for horizontal flow (θ=0) based on C_L and N_Fr
        current_flow_pattern: FlowPatternEnum
        if ((C_L < 0.01) and (N_Fr < L1)) or ((C_L >= 0.01) and (N_Fr < L2)):
            flow_regime = "Segregated"
            current_flow_pattern = FlowPatternEnum.STRATIFIED
        elif ((0.01 <= C_L < 0.4) and (L3 < N_Fr <= L1)) or ((C_L >= 0.4) and (L3 < N_Fr <= L4)):
            flow_regime = "Intermittent"
            current_flow_pattern = FlowPatternEnum.SLUG
        elif (N_Fr > L4) or ((C_L < 0.4) and (N_Fr >= L4) and (L3 < N_Fr)):  # covers very high velocity cases
            flow_regime = "Distributed"
            current_flow_pattern = FlowPatternEnum.BUBBLE
        elif (L2 < N_Fr < L3):
            flow_regime = "Transition"
            current_flow_pattern = FlowPatternEnum.TRANSITION
        else:
            # Default to Distributed if none of the above (this also covers rare edge cases)
            flow_regime = "Distributed"
            current_flow_pattern = FlowPatternEnum.BUBBLE

        # 4. Liquid holdup for horizontal flow (H_L0 at θ=0)
        # Correlation parameters for H_L0 = a * C_L^b / N_Fr^c (from Beggs & Brill)
        reg_params = {
            "Segregated":  (0.98,  0.4846, 0.0868),
            "Intermittent": (0.845, 0.5351, 0.0173),
            "Distributed": (1.065, 0.5824, 0.0609)
        }

        if flow_regime == "Transition":
            # For transition flow, interpolate liquid holdup between segregated and intermittent regimes
            a_seg, b_seg, c_seg = reg_params["Segregated"]
            a_int, b_int, c_int = reg_params["Intermittent"]
            H_L0_seg = a_seg * (C_L ** b_seg) / (N_Fr ** c_seg)
            H_L0_int = a_int * (C_L ** b_int) / (N_Fr ** c_int)
            # Weighting factor A for how close N_Fr is to the upper boundary L3 (per original correlation)
            A = (L3 - N_Fr) / (L3 - L2) if (L3 != L2) else 0.5
            H_L0 = A * H_L0_seg + (1.0 - A) * H_L0_int
        else:
            a, b, c = reg_params.get(flow_regime, reg_params["Distributed"])
            H_L0 = a * (C_L ** b) / (N_Fr ** c)

        # Ensure horizontal holdup is not less than input liquid fraction (physical constraint)
        H_L0 = max(H_L0, C_L)

        # 5. Inclination correction factor B(θ) for liquid holdup at angle θ
        # θ is now in Beggs & Brill convention (from horizontal, positive for uphill)
        
        # Determine uphill vs downhill flow for Beta calculation
        beta = 0.0
        if theta_rad > 1e-6:  # upward inclined flow (treat very small angles as horizontal)
            if flow_regime == "Segregated":
                # Uphill coefficients (Beggs & Brill original)
                D, e, f, g = 0.011, -3.768, 3.539, -1.614
            elif flow_regime == "Intermittent":
                D, e, f, g = 2.96, 0.305, -0.4473, 0.0978
            else:
                # Distributed (uphill): no correction (beta = 0)
                D, e, f, g = 1.0, 0.0, 0.0, 0.0
            beta = (1.0 - C_L) * math.log(D * (C_L ** e) * (N_LV ** f) * (N_Fr ** g)) if D != 1.0 or e != 0 else 0.0
        elif theta_rad < -1e-6:  # downward inclined flow
            # Downhill (all flow regimes use the same correlation)
            D, e, f, g = 4.7, -0.3692, 0.1244, -0.5056
            beta = (1.0 - C_L) * math.log(D * (C_L ** e) * (N_LV ** f) * (N_Fr ** g))
        else:
            beta = 0.0  # horizontal (no inclination correction needed)

        # Ensure beta is non-negative (per documentation, beta >= 0)
        if beta < 0.0:
            beta = 0.0

        # Compute B(θ) using Beta and inclination angle θ (in radians)
        B_theta = 1.0 + beta * (math.sin(1.8 * theta_rad) - (1.0/3.0) * (math.sin(1.8 * theta_rad) ** 3))

        # 6. Liquid holdup at actual inclination θ
        H_L = H_L0 * B_theta
        # Constrain holdup between 0 and 1 (avoid unphysical values)
        H_L = max(0.01, min(0.99, H_L))  # avoid exactly 0 or 1 for numerical stability
        holdups[i] = H_L

        # 7. Mixture properties for pressure gradient calculation
        # Mixture densities:
        rho_ns = C_L * liquid_density + (1.0 - C_L) * gas_density   # no-slip mixture density (lbm/ft³)
        rho_s  = H_L * liquid_density + (1.0 - H_L) * gas_density    # in-situ (slip) mixture density (lbm/ft³)
        mixture_densities[i] = rho_s
        mixture_velocities[i] = v_m

        # No-slip mixture viscosity (linear blend by input fractions)
        mu_ns = C_L * liquid_viscosity + (1.0 - C_L) * gas_viscosity

        # --- Pressure gradient components ---
        # (a) Elevation (hydrostatic) pressure gradient (psi/ft)
        dp_dz_elev = rho_s * g * math.sin(theta_rad) / (144.0 * g_c)  # 144 to convert lb/ft² to psi
        dpdz_elevation[i] = dp_dz_elev

        # (b) Frictional pressure gradient (psi/ft)
        # Reynolds number for no-slip mixture
        Re_ns = (rho_ns * v_m * tubing_diameter) / (mu_ns + 1e-20)
        reynolds_numbers[i] = Re_ns

        # Friction factor for no-slip flow (using Colebrook-White for turbulent, or laminar if low Re)
        if Re_ns < 2100.0:
            f_ns = 64.0 / Re_ns  # laminar (Darcy friction factor)
        else:
            # Colebrook-White (iterative or approximation). Use Haaland explicit approximation for speed:
            f_ns = (-1.8 * math.log10((roughness_rel/3.7) ** 1.11 + 6.9 / Re_ns)) ** -2

        # Two-phase friction factor adjustment (Beggs & Brill correlation)
        # Define Y = C_L / (H_L)^2
        Y = C_L / (H_L ** 2 + 1e-20)
        if 1.0 < Y < 1.2:
            S = math.log(2.2 * Y - 1.2)
        else:
            lnY = math.log(Y + 1e-20)
            # Polynomial fit (original correlation)
            S = lnY / (-0.0523 + 3.182 * lnY - 0.8725 * (lnY ** 2) + 0.01853 * (lnY ** 4))
        f_tp = f_ns * math.exp(S)  # two-phase friction factor (Darcy)
        friction_factors[i] = f_tp

        # Darcy-Weisbach frictional pressure gradient: ΔP/ΔL = f * (ρ_ns * v_m^2) / (2 * g_c * D) (in lbf/ft² per ft)
        # Convert to psi/ft by dividing by 144
        dp_dz_fric = f_tp * (rho_ns * v_m**2) / (2.0 * g_c * tubing_diameter * 144.0)
        dpdz_friction[i] = dp_dz_fric

        # (c) Acceleration pressure gradient is excluded in the pure correlation (Ek = 0)
        E_k = 0.0
        dp_dz_total = dp_dz_fric + dp_dz_elev  # since (1 - E_k) = 1
        dp_dz_acc = 0.0

        # Store acceleration (zero) and total gradients
        dpdz_acceleration[i] = dp_dz_acc
        dpdz_total[i] = dp_dz_total

        # Update pressure for the current segment
        current_p += dp_dz_total * segment_length
        current_md = end_md

        # Store results for the end of the segment
        pressure_profile.append(PressurePoint(
            depth=current_md,
            pressure=current_p,
            temperature=fluid.surface_temperature + fluid.temperature_gradient * current_md,
            flow_pattern=current_flow_pattern,
            liquid_holdup=H_L,
            mixture_density=rho_s,
            mixture_velocity=v_m,
            reynolds_number=Re_ns,
            friction_factor=f_tp,
            dpdz_elevation=dp_dz_elev,
            dpdz_friction=dp_dz_fric,
            dpdz_acceleration=dp_dz_acc,
            dpdz_total=dp_dz_total
        ))

    # Final calculations based on the generated profile
    bhp = pressure_profile[-1].pressure
    total_drop = bhp - surface_pressure

    # Compute overall pressure drop components by summing segment contributions
    total_elev_drop = sum(p.dpdz_elevation * (p.depth - pressure_profile[i].depth) for i, p in enumerate(pressure_profile[1:]))
    total_fric_drop = sum(p.dpdz_friction * (p.depth - pressure_profile[i].depth) for i, p in enumerate(pressure_profile[1:]))

    # Percentage contributions
    elev_pct = (total_elev_drop / total_drop * 100.0) if total_drop != 0 else 0.0
    fric_pct = (total_fric_drop / total_drop * 100.0) if total_drop != 0 else 0.0
    acc_pct = 0.0

    # Sample flow patterns from the profile for the results
    flow_pattern_results = []
    if len(pressure_profile) > 1:
        sample_interval = max(1, len(pressure_profile) // 20)
        for point in pressure_profile[::sample_interval]:
            # Need to get v_sl and v_sg for this point, for now using last calculated values
            flow_pattern_results.append(FlowPatternResult(
                depth=point.depth,
                flow_pattern=point.flow_pattern or FlowPatternEnum.BUBBLE,
                liquid_holdup=point.liquid_holdup,
                mixture_velocity=point.mixture_velocity,
                superficial_liquid_velocity=v_sl, # Note: This is the value from the last segment
                superficial_gas_velocity=v_sg  # Note: This is the value from the last segment
            ))

    return HydraulicsResult(
        method="Beggs-Brill (Pure)",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=bhp,
        overall_pressure_drop=total_drop,
        elevation_drop_percentage=elev_pct,
        friction_drop_percentage=fric_pct,
        acceleration_drop_percentage=acc_pct,
        flow_patterns=flow_pattern_results
    )