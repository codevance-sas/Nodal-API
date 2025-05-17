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

    # Set up depth points for calculation
    depth_steps = wellbore.depth_steps
    depth_points = np.linspace(0, wellbore.depth, depth_steps)

    # Initialize result arrays
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

    # Initial conditions at surface
    pressures[0] = surface_pressure
    temperatures[0] = fluid.surface_temperature

    # Compute temperature profile (linear gradient assumption)
    for i in range(depth_steps):
        temperatures[i] = fluid.surface_temperature + fluid.temperature_gradient * depth_points[i]

    # Unit conversion constants and geometry
    g_c = 32.17    # ft·lbm/(lbf·s^2), unit conversion factor
    g = 32.2       # ft/s^2, gravitational acceleration
    tubing_diameter = wellbore.tubing_id / 12.0  # convert tubing ID from inches to ft
    tubing_area = math.pi * (tubing_diameter / 2.0) ** 2
    roughness_rel = wellbore.roughness / (wellbore.tubing_id * 12.0)  # relative roughness (ft/ft)

    # Stepwise calculation down the wellbore
    for i in range(depth_steps - 1):
        # Current state at depth step i
        p = pressures[i]
        T = temperatures[i]

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

        # Convert wellbore deviation (from vertical) to Beggs & Brill angle (from horizontal)
        # Wellbore deviation: 0° = vertical, 90° = horizontal
        # Beggs & Brill: 0° = horizontal, +90° = vertical up, -90° = vertical down
        wellbore_deviation = wellbore.deviation  # Angle from vertical in degrees
        beggs_brill_angle = 90.0 - wellbore_deviation  # Convert to angle from horizontal

        # Determine if flow is upward or downward
        # For a production well, flow is typically upward (toward surface)
        # For an injection well, flow would be downward
        is_upward = True  # Default assumption for production wells

        # Set the correct sign for Beggs & Brill angle
        if is_upward:
            theta = beggs_brill_angle  # Positive for upward flow (standard case for production)
        else:
            theta = -beggs_brill_angle  # Negative for downward flow (injection wells)

        # Convert to radians for trigonometric functions
        theta_rad = math.radians(theta)

        # 1. Dimensionless numbers for flow regime determination
        N_Fr = v_m**2 / (g * tubing_diameter)  # mixture Froude number
        N_LV = 1.938 * v_sl * ((liquid_density / (g * sigma)) ** 0.25)  # liquid velocity number (dimensionless)

        # 2. Flow pattern map boundaries (L1, L2, L3, L4 from Beggs & Brill)
        L1 = 316.0 * (C_L ** 0.302)
        L2 = 0.0009252 * (C_L ** -2.4684)
        L3 = 0.10 * (C_L ** -1.4516)
        L4 = 0.50 * (C_L ** -6.738)

        # 3. Determine flow regime for horizontal flow (θ=0) based on C_L and N_Fr
        if ((C_L < 0.01) and (N_Fr < L1)) or ((C_L >= 0.01) and (N_Fr < L2)):
            flow_regime = "Segregated"
            flow_patterns[i] = FlowPatternEnum.STRATIFIED
        elif ((0.01 <= C_L < 0.4) and (L3 < N_Fr <= L1)) or ((C_L >= 0.4) and (L3 < N_Fr <= L4)):
            flow_regime = "Intermittent"
            flow_patterns[i] = FlowPatternEnum.SLUG
        elif (N_Fr > L4) or ((C_L < 0.4) and (N_Fr >= L4) and (L3 < N_Fr)):  # covers very high velocity cases
            flow_regime = "Distributed"
            flow_patterns[i] = FlowPatternEnum.BUBBLE
        elif (L2 < N_Fr < L3):
            flow_regime = "Transition"
            flow_patterns[i] = FlowPatternEnum.TRANSITION
        else:
            # Default to Distributed if none of the above (this also covers rare edge cases)
            flow_regime = "Distributed"
            flow_patterns[i] = FlowPatternEnum.BUBBLE

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

        # Update pressure to next depth point using the total pressure gradient
        dz = depth_points[i+1] - depth_points[i]
        pressures[i+1] = pressures[i] + dp_dz_total * dz

    # Fill in the last point's stored values (at bottomhole, index depth_steps-1)
    holdups[-1] = holdups[-2]
    flow_patterns[-1] = flow_patterns[-2] or FlowPatternEnum.BUBBLE
    mixture_densities[-1] = mixture_densities[-2]
    mixture_velocities[-1] = mixture_velocities[-2]
    friction_factors[-1] = friction_factors[-2]
    reynolds_numbers[-1] = reynolds_numbers[-2]
    dpdz_elevation[-1] = dpdz_elevation[-2]
    dpdz_friction[-1] = dpdz_friction[-2]
    dpdz_acceleration[-1] = 0.0
    dpdz_total[-1] = dpdz_elevation[-1] + dpdz_friction[-1]

    # Build the PressurePoint list for the pressure profile
    pressure_profile = []
    for i in range(depth_steps):
        pressure_profile.append(PressurePoint(
            depth=depth_points[i],
            pressure=pressures[i],
            temperature=temperatures[i],
            flow_pattern=flow_patterns[i],
            liquid_holdup=holdups[i],
            mixture_density=mixture_densities[i],
            mixture_velocity=mixture_velocities[i],
            reynolds_number=reynolds_numbers[i],
            friction_factor=friction_factors[i],
            dpdz_elevation=dpdz_elevation[i],
            dpdz_friction=dpdz_friction[i],
            dpdz_acceleration=dpdz_acceleration[i],
            dpdz_total=dpdz_total[i]
        ))

    # Compute overall pressure drop components by integrating gradients over the wellbore
    total_elev = np.trapz(dpdz_elevation, depth_points)  if depth_steps > 1 else dpdz_elevation[0] * wellbore.depth
    total_fric = np.trapz(dpdz_friction, depth_points)   if depth_steps > 1 else dpdz_friction[0] * wellbore.depth
    total_acc = 0.0  # no acceleration component in pure correlation
    total_drop = total_elev + total_fric + total_acc

    # Percentage contributions (avoid division by zero)
    elev_pct = (total_elev / total_drop * 100.0) if total_drop != 0 else 0.0
    fric_pct = (total_fric / total_drop * 100.0) if total_drop != 0 else 0.0
    acc_pct  = 0.0

    # (Optional) Prepare sampled flow pattern results (e.g., every 10th point for visualization)
    flow_pattern_results = []
    sample_interval = max(1, depth_steps // 20)
    for j in range(0, depth_steps, sample_interval):
        flow_pattern_results.append(FlowPatternResult(
            depth=depth_points[j],
            flow_pattern=flow_patterns[j] or FlowPatternEnum.BUBBLE,
            liquid_holdup=holdups[j],
            mixture_velocity=mixture_velocities[j],
            superficial_liquid_velocity=v_sl,
            superficial_gas_velocity=v_sg
        ))

    # Return the results in a HydraulicsResult object
    return HydraulicsResult(
        method="Beggs-Brill (Pure)",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=elev_pct,
        friction_drop_percentage=fric_pct,
        acceleration_drop_percentage=acc_pct,
        flow_patterns=flow_pattern_results
    )