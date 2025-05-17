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
def calculate_gray(data: HydraulicsInput) -> HydraulicsResult:
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
    dpdz_acceleration = np.zeros(depth_steps)
    dpdz_total = np.zeros(depth_steps)
    vsl_array = np.zeros(depth_steps)
    vsg_array = np.zeros(depth_steps)

    pressures[0] = surface_pressure

    g_c = 32.17
    g = 32.2
    D = wellbore.tubing_id / 12.0
    A = math.pi * (D / 2.0)**2
    roughness_rel = wellbore.roughness / (wellbore.tubing_id * 12.0)

    for i in range(depth_steps - 1):
        p = pressures[i]
        T = temperatures[i]

        props = calculate_fluid_properties(
            p, T, {
                "oil_gravity": fluid.oil_gravity,
                "gas_gravity": fluid.gas_gravity,
                "bubble_point": fluid.bubble_point,
                "water_gravity": fluid.water_gravity
            }
        )

        Qo = fluid.oil_rate * 5.615 * props["oil_fvf"]
        Qw = fluid.water_rate * 5.615 * props["water_fvf"]
        Qg = fluid.gas_rate * 1000.0 * props["gas_fvf"]

        v_sl = (Qo + Qw) / (86400 * A)
        v_sg = Qg / (86400 * A)
        v_m = v_sl + v_sg
        vsl_array[i] = v_sl
        vsg_array[i] = v_sg

        C_L = v_sl / (v_sl + v_sg + 1e-10)

        rho_o = 62.4 / props["oil_fvf"]
        rho_w = 62.4 * fluid.water_gravity / props["water_fvf"]
        rho_g = 0.0764 * fluid.gas_gravity / props["gas_fvf"]

        total_liquid = fluid.oil_rate + fluid.water_rate
        rho_l = (fluid.oil_rate * rho_o + fluid.water_rate * rho_w) / total_liquid
        mu_l = (fluid.oil_rate * props["oil_viscosity"] + fluid.water_rate * props["water_viscosity"]) / total_liquid

        sigma_oil_gas = max(1.0, 30.0 - 0.1 * (T - 60.0) - 0.005 * (p - 14.7))
        sigma_water_gas = max(5.0, 70.0 - 0.15 * (T - 60.0) - 0.01 * (p - 14.7))
        sigma = (fluid.oil_rate * sigma_oil_gas + fluid.water_rate * sigma_water_gas) / total_liquid
        sigma_lbf_ft = sigma * 6.85e-5

        R = v_sl / (v_sg + 1e-10)
        N_v = (rho_l**2 * v_m**2) / (g * sigma_lbf_ft * (rho_l - rho_g))
        N_d = g * (rho_l - rho_g) * D**2 / sigma_lbf_ft

        A, B, C, D_g = 0.0814, -0.821, 0.4846, -0.0868

        if R > 0.01:
            H_L = 1.0 / (1.0 + A * (R**B) * (N_v**C) * (N_d**D_g))
        else:
            H_L = 0.01 + 0.99 * R

        H_L = max(0.01, min(0.99, H_L))
        holdups[i] = H_L

        if H_L < 0.1:
            flow_patterns[i] = FlowPatternEnum.MIST
        elif H_L < 0.25:
            flow_patterns[i] = FlowPatternEnum.ANNULAR
        elif H_L < 0.45:
            flow_patterns[i] = FlowPatternEnum.TRANSITION
        else:
            flow_patterns[i] = FlowPatternEnum.SLUG

        rho_ns = C_L * rho_l + (1 - C_L) * rho_g
        rho_s = H_L * rho_l + (1 - H_L) * rho_g
        mu_ns = C_L * mu_l + (1 - C_L) * props["gas_viscosity"]

        k0 = 28.5 * sigma_lbf_ft / (rho_ns * v_m**2)
        k_eff = max(roughness_rel + k0, 2.77e-5)

        Re = (rho_ns * v_m * D) / (mu_ns + 1e-10)
        reynolds_numbers[i] = Re

        if Re > 2100:
            f_D = (-1.8 * math.log10(((k_eff/3.7)**1.11) + (6.9/Re)))**-2
        else:
            f_D = 64.0 / Re
        friction_factors[i] = f_D

        dpdz_elevation[i] = rho_s * g / (144.0 * g_c)
        dpdz_friction[i] = f_D * rho_ns * v_m**2 / (2 * g_c * D * 144.0)
        dpdz_acceleration[i] = 0.0  # Neglect for now
        dpdz_total[i] = dpdz_elevation[i] + dpdz_friction[i]

        dz = depth_points[i+1] - depth_points[i]
        pressures[i+1] = pressures[i] + dpdz_total[i] * dz
        mixture_densities[i] = rho_s
        mixture_velocities[i] = v_m

    pressure_profile = [
        PressurePoint(
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
        ) for i in range(depth_steps)
    ]

    dz = wellbore.depth / (depth_steps - 1)
    total_elev = sum(dpdz_elevation) * dz
    total_fric = sum(dpdz_friction) * dz
    total_drop = total_elev + total_fric

    flow_pattern_results = [
        FlowPatternResult(
            depth=depth_points[i],
            flow_pattern=flow_patterns[i] or FlowPatternEnum.MIST,
            liquid_holdup=holdups[i],
            mixture_velocity=mixture_velocities[i],
            superficial_liquid_velocity=vsl_array[i],
            superficial_gas_velocity=vsg_array[i]
        ) for i in range(0, depth_steps, max(1, depth_steps // 20))
    ]

    return HydraulicsResult(
        method="Gray",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=(total_elev / total_drop) * 100 if total_drop > 0 else 0,
        friction_drop_percentage=(total_fric / total_drop) * 100 if total_drop > 0 else 0,
        acceleration_drop_percentage=0.0,
        flow_patterns=flow_pattern_results
    )
