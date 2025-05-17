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

def calculate_hagedorn_brown(data: HydraulicsInput) -> HydraulicsResult:
    """
    Pure Hagedorn-Brown vertical multiphase flow correlation implementation.
    This version excludes acceleration pressure drop and follows the original
    methodology as closely as possible based on literature and IHS documentation.
    """
    fluid = data.fluid_properties
    wellbore = data.wellbore_geometry
    surface_pressure = data.surface_pressure

    depth_steps = wellbore.depth_steps
    depth_points = np.linspace(0, wellbore.depth, depth_steps)

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
    dpdz_total = np.zeros(depth_steps)

    pressures[0] = surface_pressure
    temperatures = fluid.surface_temperature + fluid.temperature_gradient * depth_points

    g = 32.2
    g_c = 32.17
    PI = math.pi
    D = wellbore.tubing_id / 12
    A = PI * (D/2)**2
    roughness_rel = wellbore.roughness / (wellbore.tubing_id * 12)

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
        Qg = fluid.gas_rate * 1000 * props["gas_fvf"]

        v_sl = (Qo + Qw) / (86400 * A)
        v_sg = Qg / (86400 * A)
        v_m = v_sl + v_sg

        C_L = v_sl / (v_sl + v_sg + 1e-10)

        rho_o = 62.4 / props["oil_fvf"]
        rho_w = 62.4 * fluid.water_gravity / props["water_fvf"]
        rho_g = 0.0764 * fluid.gas_gravity / props["gas_fvf"]

        q_tot_liq = fluid.oil_rate + fluid.water_rate
        rho_liq = (fluid.oil_rate * rho_o + fluid.water_rate * rho_w) / q_tot_liq
        mu_liq = (fluid.oil_rate * props["oil_viscosity"] + fluid.water_rate * props["water_viscosity"]) / q_tot_liq

        psi = (30.0 - 0.1 * (T - 60) - 0.005 * (p - 14.7))
        psi = max(1.0, psi)
        psi = (psi / (g_c * (rho_liq - rho_g) * D))**0.25

        CN_mu = (mu_liq / props["gas_viscosity"])**0.1
        N_lv = v_sl * (rho_liq / rho_g)**0.25
        N_gv = v_sg * (rho_liq / rho_g)**0.25

        L = 0.0055 * (N_lv**0.1) * (CN_mu**0.5) * (psi**0.7)
        if L > 0.025:
            L = 0.0055 * (N_lv**0.1) * (CN_mu**0.5) * (psi**-2.3)

        if N_gv <= 0.1:
            H_L = 1.0 - N_gv / (1.0 + 75.0 * L)
        elif N_gv <= 1.0:
            H_L = 1.0 - N_gv / (1.0 + 75.0 * L * (N_gv**-0.5))
        elif N_gv <= 10.0:
            H_L = 1.0 - N_gv / (1.0 + 75.0 * L * (N_gv**-0.75))
        else:
            H_L = 1.0 - N_gv / (1.0 + 75.0 * L * (N_gv**-1.0))

        H_L = max(0.01, min(0.99, H_L))
        holdups[i] = H_L

        if H_L > 0.8:
            flow_patterns[i] = FlowPatternEnum.BUBBLE
        elif H_L > 0.3:
            flow_patterns[i] = FlowPatternEnum.SLUG
        elif H_L > 0.1:
            flow_patterns[i] = FlowPatternEnum.TRANSITION
        else:
            flow_patterns[i] = FlowPatternEnum.ANNULAR

        rho_s = H_L * rho_liq + (1 - H_L) * rho_g
        rho_ns = C_L * rho_liq + (1 - C_L) * rho_g
        mixture_densities[i] = rho_s
        mixture_velocities[i] = v_m

        mu_m = mu_liq**H_L * props["gas_viscosity"]**(1 - H_L)
        Re = (rho_s * v_m * D) / (mu_m + 1e-10)
        reynolds_numbers[i] = Re

        if Re > 2100:
            f = (-1.8 * math.log10((roughness_rel/3.7)**1.11 + 6.9/Re))**-2
        else:
            f = 64.0 / Re
        friction_factors[i] = f

        dpdz_elevation[i] = rho_s * g / (144.0 * g_c)
        dpdz_friction[i] = f * rho_s * v_m**2 / (2 * g_c * D * 144.0)
        dpdz_total[i] = dpdz_elevation[i] + dpdz_friction[i]

        dz = depth_points[i+1] - depth_points[i]
        pressures[i+1] = pressures[i] + dpdz_total[i] * dz

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
    total_elevation = sum(dpdz_elevation) * dz
    total_friction = sum(dpdz_friction) * dz
    total_drop = total_elevation + total_friction

    return HydraulicsResult(
        method="Hagedorn-Brown (Pure)",
        pressure_profile=pressure_profile,
        surface_pressure=surface_pressure,
        bottomhole_pressure=pressures[-1],
        overall_pressure_drop=pressures[-1] - surface_pressure,
        elevation_drop_percentage=(total_elevation / total_drop) * 100 if total_drop > 0 else 0,
        friction_drop_percentage=(total_friction / total_drop) * 100 if total_drop > 0 else 0,
        acceleration_drop_percentage=0.0,
        flow_patterns=[
            FlowPatternResult(
                depth=depth_points[i],
                flow_pattern=flow_patterns[i] or FlowPatternEnum.BUBBLE,
                liquid_holdup=holdups[i],
                mixture_velocity=mixture_velocities[i],
                superficial_liquid_velocity=v_sl,
                superficial_gas_velocity=v_sg
            ) for i in range(0, depth_steps, max(1, depth_steps // 20))
        ]
    )
