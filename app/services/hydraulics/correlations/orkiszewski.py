import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class Orkiszewski(CorrelationBase):
    """
    Implementation of Orkiszewski correlation for multiphase flow
    with flow pattern prediction and pressure drop calculation
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Orkiszewski"
        self.survey_data = data.survey_data
        if self.survey_data:
            self.survey_data.sort(key=lambda s: s.md)
            
    def _calculate_survey_segment(self, depth: float):
        """Find the appropriate survey segment for a given depth"""
        if not self.survey_data:
            return None
        for i in range(len(self.survey_data) - 1):
            if self.survey_data[i].md <= depth < self.survey_data[i+1].md:
                return self.survey_data[i]
        return self.survey_data[-1]
    
    def calculate_pressure_profile(self):
        """
        Calculate pressure profile using the Orkiszewski correlation
        """
        # Calculation loop - march down the wellbore
        for i in range(self.depth_steps - 1):
            # Current conditions
            p = self.pressures[i]
            T = self.temperatures[i]
            depth = self.depth_points[i]
            
            # Find the correct pipe and survey segment for the current depth
            pipe_segment = self._calculate_pipe_segment(depth)
            survey_segment = self._calculate_survey_segment(depth) if self.survey_data else None
            
            # Get pipe properties
            D = pipe_segment.diameter / 12.0  # Convert tubing ID from inches to ft
            A = self.PI * (D / 2.0) ** 2
            roughness_rel = self.wellbore.roughness / pipe_segment.diameter
            
            # Calculate inclination angle (from vertical)
            inclination_rad = math.radians(survey_segment.inclination if survey_segment else self.wellbore.deviation)
            
            # Calculate fluid properties
            props = self._calculate_fluid_properties(p, T)
            Qo, Qw, Qg = self._convert_production_rates(props)
            v_sl, v_sg, v_m = self._calculate_superficial_velocities(Qo, Qw, Qg, A)
            self.v_sl_profile[i] = v_sl
            self.v_sg_profile[i] = v_sg
            
            # Calculate input liquid fraction (no-slip holdup)
            C_L = v_sl / (v_sl + v_sg + 1e-10)
            
            # Calculate fluid densities and liquid properties
            rho_o, rho_w, rho_g = self._calculate_fluid_densities(props)
            rho_liq, mu_liq = self._calculate_liquid_properties(rho_o, rho_w, props)
            
            # Calculate surface tension
            sigma_oil_gas = max(1.0, 30.0 - 0.1 * (T - 60.0) - 0.005 * (p - 14.7))
            sigma_water_gas = max(5.0, 70.0 - 0.15 * (T - 60.0) - 0.01 * (p - 14.7))
            
            # Weighted surface tension
            total_liquid_rate = self.fluid.oil_rate + self.fluid.water_rate
            if total_liquid_rate > 0:
                oil_fraction = self.fluid.oil_rate / total_liquid_rate
                water_fraction = self.fluid.water_rate / total_liquid_rate
                sigma = oil_fraction * sigma_oil_gas + water_fraction * sigma_water_gas
            else:
                sigma = sigma_oil_gas  # Default to oil-gas if no liquid
                
            # Convert surface tension from dynes/cm to lbf/ft
            sigma_lbf_ft = sigma * 6.85e-5
            
            # Approximate slip velocity
            v_s = max(0.1, min(1.2, 0.35 * (sigma_lbf_ft * self.G * (rho_liq - rho_g) / (rho_liq**2))**0.25))
            L_b = 1.071 - 0.2218 * (v_m / v_s)**2
            
            # Flow regime classification
            if v_sg < v_s * (L_b - v_sl / v_s):
                regime = "Bubble"
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE
            elif v_sg < 0.75:
                regime = "Slug"
                self.flow_patterns[i] = FlowPatternEnum.SLUG
            elif v_sg < 10.0:
                regime = "Transition"
                self.flow_patterns[i] = FlowPatternEnum.TRANSITION
            else:
                regime = "Annular"
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR
            
            # Liquid holdup by regime
            if regime == "Bubble":
                H_L = 1.0 - 0.5 * (v_sg / (v_sg + v_s))
            elif regime == "Slug":
                v_tb = 0.52 * (self.G * D * (rho_liq - rho_g) / rho_liq)**0.5
                beta = v_sl / (v_m + v_tb)
                H_L = beta + (1.0 - beta) * v_sl / (v_sg + v_sl + v_tb)
            elif regime == "Transition":
                H_L_slug = 0.5 * (1.0 + v_sl / (v_sl + v_sg))
                H_L_ann = C_L
                t = (v_sg - 0.75) / (10.0 - 0.75)
                H_L = H_L_slug * (1 - t) + H_L_ann * t
            else:  # Annular
                H_L = max(C_L * 0.6, 0.05)
            
            # Ensure holdup is within physical limits
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Mixture properties
            rho_s = H_L * rho_liq + (1 - H_L) * rho_g
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m
            
            # Reynolds number calculation based on flow regime
            if regime in ["Bubble", "Slug"]:
                Re = (rho_liq * v_m * D) / mu_liq
            elif regime == "Transition":
                mu_m = C_L * mu_liq + (1 - C_L) * props["gas_viscosity"]
                Re = (rho_s * v_m * D) / (mu_m + 1e-10)
            else:
                Re = (rho_g * v_m * D) / props["gas_viscosity"]
            
            self.reynolds_numbers[i] = Re
            
            # Calculate friction factor
            self.friction_factors[i] = self._calculate_friction_factor(Re, roughness_rel)
            
            # Pressure gradient components
            # Hydrostatic component (psi/ft) - adjusted for inclination
            self.dpdz_elevation[i] = rho_s * self.G * math.cos(inclination_rad) / (144.0 * self.G_C)
            
            # Friction component (psi/ft)
            self.dpdz_friction[i] = self.friction_factors[i] * rho_s * v_m**2 / (2.0 * self.G_C * D * 144.0)
            
            # Acceleration component (psi/ft) - neglected in Orkiszewski
            self.dpdz_acceleration[i] = 0.0
            
            # Total pressure gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i]
            
            # Calculate next pressure
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = p + self.dpdz_total[i] * dz

def calculate_orkiszewski(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile using the Orkiszewski correlation
    """
    correlation = Orkiszewski(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()
