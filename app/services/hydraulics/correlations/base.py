from app.schemas.hydraulics import HydraulicsInput, HydraulicsResult, PressurePoint, FlowPatternEnum, FlowPatternResult
from ..utils import calculate_fluid_properties
import math
import numpy as np
from abc import ABC, abstractmethod

class CorrelationBase(ABC):
    PI = math.pi
    G = 32.2
    G_C = 32.17
    
    def __init__(self, data: HydraulicsInput):
        self.data = data    
        self.fluid = data.fluid_properties
        self.wellbore = data.wellbore_geometry
        # Sort pipe segments by start_depth to ensure correct processing order
        self.wellbore.pipe_segments.sort(key=lambda s: s.start_depth)
        self.surface_pressure = data.surface_pressure

        self.depth_steps = self.wellbore.depth_steps
        self.depth_points = np.linspace(0, self.wellbore.pipe_segments[-1].end_depth, self.depth_steps)

        self.pressures = np.zeros(self.depth_steps)
        self.temperatures = np.zeros(self.depth_steps)
        self.holdups = np.zeros(self.depth_steps)
        self.flow_patterns = [None] * self.depth_steps
        self.mixture_densities = np.zeros(self.depth_steps)
        self.mixture_velocities = np.zeros(self.depth_steps)
        self.friction_factors = np.zeros(self.depth_steps)
        self.reynolds_numbers = np.zeros(self.depth_steps)
        self.dpdz_elevation = np.zeros(self.depth_steps)
        self.dpdz_friction = np.zeros(self.depth_steps)
        self.dpdz_acceleration = np.zeros(self.depth_steps)
        self.dpdz_total = np.zeros(self.depth_steps)
        self.v_sl_profile = np.zeros(self.depth_steps)
        self.v_sg_profile = np.zeros(self.depth_steps)

        self.pressures[0] = self.surface_pressure
        self.temperatures = self.fluid.surface_temperature + self.fluid.temperature_gradient * self.depth_points

    def _calculate_pipe_segment(self, depth: float):
        for segment in self.wellbore.pipe_segments:
            if segment.start_depth <= depth <= segment.end_depth:
                return segment
        return None

    def _calculate_fluid_properties(self, p: float, T: float):
        return calculate_fluid_properties(
            p, T, {
                "oil_gravity": self.fluid.oil_gravity,
                "gas_gravity": self.fluid.gas_gravity,
                "bubble_point": self.fluid.bubble_point,
                "water_gravity": self.fluid.water_gravity
            }
        )

    def _convert_production_rates(self, props):
        Qo = self.fluid.oil_rate * 5.615 * props["oil_fvf"]
        Qw = self.fluid.water_rate * 5.615 * props["water_fvf"]
        Qg = self.fluid.gas_rate * 1000 * props["gas_fvf"]
        return Qo, Qw, Qg

    def _calculate_superficial_velocities(self, Qo, Qw, Qg, A):
        v_sl = (Qo + Qw) / (86400 * A)
        v_sg = Qg / (86400 * A)
        v_m = v_sl + v_sg
        return v_sl, v_sg, v_m

    def _calculate_fluid_densities(self, props):
        rho_o = 62.4 / props["oil_fvf"]
        rho_w = 62.4 * self.fluid.water_gravity / props["water_fvf"]
        rho_g = 0.0764 * self.fluid.gas_gravity / props["gas_fvf"]
        return rho_o, rho_w, rho_g

    def _calculate_liquid_properties(self, rho_o, rho_w, props):
        q_tot_liq = self.fluid.oil_rate + self.fluid.water_rate
        rho_liq = (self.fluid.oil_rate * rho_o + self.fluid.water_rate * rho_w) / q_tot_liq if q_tot_liq > 0 else 0
        mu_liq = (self.fluid.oil_rate * props["oil_viscosity"] + self.fluid.water_rate * props["water_viscosity"]) / q_tot_liq if q_tot_liq > 0 else 0
        return rho_liq, mu_liq

    def _calculate_friction_factor(self, Re, roughness_rel):
        if Re > 2100:
            return (-1.8 * math.log10((roughness_rel / 3.7)**1.11 + 6.9 / Re))**-2
        else:
            return 64.0 / Re

    @abstractmethod
    def calculate_pressure_profile(self):
        raise NotImplementedError

    def get_results(self) -> HydraulicsResult:
        pressure_profile = [
            PressurePoint(
                depth=self.depth_points[i],
                pressure=self.pressures[i],
                temperature=self.temperatures[i],
                flow_pattern=self.flow_patterns[i],
                liquid_holdup=self.holdups[i],
                mixture_density=self.mixture_densities[i],
                mixture_velocity=self.mixture_velocities[i],
                reynolds_number=self.reynolds_numbers[i],
                friction_factor=self.friction_factors[i],
                dpdz_elevation=self.dpdz_elevation[i],
                dpdz_friction=self.dpdz_friction[i],
                dpdz_acceleration=self.dpdz_acceleration[i],
                dpdz_total=self.dpdz_total[i]
            ) for i in range(self.depth_steps)
        ]

        dz = self.wellbore.pipe_segments[-1].end_depth / (self.depth_steps - 1) if self.depth_steps > 1 else 0
        total_elevation = np.trapz(self.dpdz_elevation, self.depth_points) if self.depth_steps > 1 else 0
        total_friction = np.trapz(self.dpdz_friction, self.depth_points) if self.depth_steps > 1 else 0
        total_acceleration = np.trapz(self.dpdz_acceleration, self.depth_points) if self.depth_steps > 1 else 0
        total_drop = total_elevation + total_friction + total_acceleration

        return HydraulicsResult(
            method=self.method_name,
            pressure_profile=pressure_profile,
            surface_pressure=self.surface_pressure,
            bottomhole_pressure=self.pressures[-1],
            overall_pressure_drop=self.pressures[-1] - self.surface_pressure,
            elevation_drop_percentage=(total_elevation / total_drop) * 100 if total_drop > 0 else 0,
            friction_drop_percentage=(total_friction / total_drop) * 100 if total_drop > 0 else 0,
            acceleration_drop_percentage=(total_acceleration / total_drop) * 100 if total_drop > 0 else 0,
            flow_patterns=[
                FlowPatternResult(
                    depth=self.depth_points[i],
                    flow_pattern=self.flow_patterns[i] or FlowPatternEnum.BUBBLE,
                    liquid_holdup=self.holdups[i],
                    mixture_velocity=self.mixture_velocities[i],
                    superficial_liquid_velocity=self.v_sl_profile[i],
                    superficial_gas_velocity=self.v_sg_profile[i],
                ) for i in range(0, self.depth_steps, max(1, self.depth_steps // 20))
            ]
        )
    
    