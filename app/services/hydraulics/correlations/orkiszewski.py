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

def calculate_orkiszewski(data: HydraulicsInput) -> HydraulicsResult:
    import numpy as np
    import math

    fluid = data.fluid_properties
    wellbore = data.wellbore_geometry
    surface_pressure = data.surface_pressure

    depth_steps = wellbore.depth_steps
    depth_points = np.linspace(0, wellbore.depth, depth_steps)

    pressures = np.zeros(depth_steps)
    temperatures = fluid.surface_temperature + fluid.temperature_gradient * depth_points
    holdups = np.zeros(depth_steps)
    flow_patterns = [None] * depth_steps
    mixture_densities = np.zeros(depth_steps)
    mixture_velocities = np.zeros(depth_steps)
    friction_factors = np.zeros(depth_steps)
    reynolds_numbers = np.zeros(depth_steps)
    dpdz_elevation = np.zeros(depth_steps)
    dpdz_friction = np.zeros(depth_steps)
    dpdz_total = np.zeros(depth_steps)

    g = 32.2
    g_c = 32.17
    D = wellbore.tubing_id / 12.0
    A = math.pi * (D / 2.0)**2
    roughness_rel = wellbore.roughness / (wellbore.tubing_id * 12.0)

    pressures[0] = surface_pressure

    for i in range(depth_steps - 1):
        p = pressures[i]
        T = temperatures[i]

        props = calculate_fluid_properties(p, T, {
            "oil_gravity": fluid.oil_gravity,
            "gas_gravity": fluid.gas_gravity,
            "bubble_point": fluid.bubble_point,
            "water_gravity": fluid.water_gravity
        })

        Qo = fluid.oil_rate * 5.615 * props["oil_fvf"]
        Qw = fluid.water_rate * 5.615 * props["water_fvf"]
        Qg = fluid.gas_rate * 1000.0 * props["gas_fvf"]

        v_sl = (Qo + Qw) / (86400 * A)
        v_sg = Qg / (86400 * A)
        v_m = v_sl + v_sg
        C_L = v_sl / (v_sl + v_sg + 1e-10)

        rho_o = 62.4 / props["oil_fvf"]
        rho_w = 62.4 * fluid.water_gravity / props["water_fvf"]
        rho_g = 0.0764 * fluid.gas_gravity / props["gas_fvf"]
        rho_l = (fluid.oil_rate * rho_o + fluid.water_rate * rho_w) / (fluid.oil_rate + fluid.water_rate)
        mu_l = (fluid.oil_rate * props["oil_viscosity"] + fluid.water_rate * props["water_viscosity"]) / (fluid.oil_rate + fluid.water_rate)

        sigma_oil_gas = max(1.0, 30.0 - 0.1 * (T - 60) - 0.005 * (p - 14.7))
        sigma_water_gas = max(5.0, 70.0 - 0.15 * (T - 60) - 0.01 * (p - 14.7))
        sigma = (fluid.oil_rate * sigma_oil_gas + fluid.water_rate * sigma_water_gas) / (fluid.oil_rate + fluid.water_rate)
        sigma_lbf_ft = sigma * 6.85e-5

        # Approximate slip velocity
        v_s = max(0.1, min(1.2, 0.35 * (sigma_lbf_ft * g * (rho_l - rho_g) / (rho_l**2))**0.25))
        L_b = 1.071 - 0.2218 * (v_m / v_s)**2

        # Flow regime classification
        if v_sg < v_s * (L_b - v_sl / v_s):
            regime = "Bubble"
            flow_patterns[i] = FlowPatternEnum.BUBBLE
        elif v_sg < 0.75:
            regime = "Slug"
            flow_patterns[i] = FlowPatternEnum.SLUG
        elif v_sg < 10.0:
            regime = "Transition"
            flow_patterns[i] = FlowPatternEnum.TRANSITION
        else:
            regime = "Annular"
            flow_patterns[i] = FlowPatternEnum.ANNULAR

        # Liquid holdup by regime
        if regime == "Bubble":
            H_L = 1.0 - 0.5 * (v_sg / (v_sg + v_s))
        elif regime == "Slug":
            v_tb = 0.52 * (g * D * (rho_l - rho_g) / rho_l)**0.5
            beta = v_sl / (v_m + v_tb)
            H_L = beta + (1.0 - beta) * v_sl / (v_sg + v_sl + v_tb)
        elif regime == "Transition":
            H_L_slug = 0.5 * (1.0 + v_sl / (v_sl + v_sg))
            H_L_ann = C_L
            t = (v_sg - 0.75) / (10.0 - 0.75)
            H_L = H_L_slug * (1 - t) + H_L_ann * t
        else:  # Annular
            H_L = max(C_L * 0.6, 0.05)

        H_L = max(0.01, min(0.99, H_L))
        holdups[i] = H_L

        rho_s = H_L * rho_l + (1 - H_L) * rho_g
        mixture_densities[i] = rho_s
        mixture_velocities[i] = v_m

        if regime in ["Bubble", "Slug"]:
            Re = (rho_l * v_m * D) / mu_l
        elif regime == "Transition":
            mu_m = C_L * mu_l + (1 - C_L) * props["gas_viscosity"]
            Re = (rho_s * v_m * D) / (mu_m + 1e-10)
        else:
            Re = (rho_g * v_m * D) / props["gas_viscosity"]

        reynolds_numbers[i] = Re

        if Re > 2100:
            f = (-1.8 * math.log10((roughness_rel / 3.7)**1.11 + 6.9 / Re))**-2
        else:
            f = 64.0 / Re
        friction_factors[i] = f

        dpdz_elevation[i] = rho_s * g * np.sin(np.radians(wellbore.deviation)) / (144.0 * g_c)
        dpdz_friction[i] = f * rho_s * v_m**2 / (2 * g_c * D * 144.0)
        dpdz_total[i] = dpdz_elevation[i] + dpdz_friction[i]

        dz = depth_points[i+1] - depth_points[i]
        pressures[i+1] = pressures[i] + dpdz_total[i] * dz

    # Build result structure
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
            dpdz_acceleration=0.0,
            dpdz_total=dpdz_total[i]
        ))

    dz = wellbore.depth / (depth_steps - 1)
    total_elev = sum(dpdz_elevation) * dz
    total_fric = sum(dpdz_friction) * dz
    total_drop = total_elev + total_fric

    flow_pattern_results = [
        FlowPatternResult(
            depth=depth_points[i],
            flow_pattern=flow_patterns[i] or FlowPatternEnum.BUBBLE,
            liquid_holdup=holdups[i],
            mixture_velocity=mixture_velocities[i],
            superficial_liquid_velocity=v_sl,
            superficial_gas_velocity=v_sg
        ) for i in range(0, depth_steps, max(1, depth_steps // 20))
    ]

    return HydraulicsResult(
        method="Orkiszewski",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=(total_elev / total_drop) * 100 if total_drop > 0 else 0,
        friction_drop_percentage=(total_fric / total_drop) * 100 if total_drop > 0 else 0,
        acceleration_drop_percentage=0.0,
        flow_patterns=flow_pattern_results
    )
