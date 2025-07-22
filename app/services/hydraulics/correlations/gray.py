import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class Gray(CorrelationBase):
    """
    Implementation of Gray correlation for multiphase flow
    with flow pattern prediction and pressure drop calculation
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Gray"
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
        Calculate pressure profile using the Gray correlation
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
            
            # Gray correlation parameters
            R = v_sl / (v_sg + 1e-10)  # Liquid to gas ratio
            N_v = (rho_liq**2 * v_m**2) / (self.G * sigma_lbf_ft * (rho_liq - rho_g))  # Velocity number
            N_d = self.G * (rho_liq - rho_g) * D**2 / sigma_lbf_ft  # Diameter number
            
            # Gray correlation constants
            A_gray, B, C, D_g = 0.0814, -0.821, 0.4846, -0.0868
            
            # Calculate liquid holdup
            if R > 0.01:
                H_L = 1.0 / (1.0 + A_gray * (R**B) * (N_v**C) * (N_d**D_g))
            else:
                H_L = 0.01 + 0.99 * R
            
            # Ensure holdup is within physical limits
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Determine flow pattern based on holdup
            if H_L < 0.1:
                self.flow_patterns[i] = FlowPatternEnum.MIST
            elif H_L < 0.25:
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR
            elif H_L < 0.45:
                self.flow_patterns[i] = FlowPatternEnum.TRANSITION
            else:
                self.flow_patterns[i] = FlowPatternEnum.SLUG
            
            # Calculate mixture properties
            rho_ns = C_L * rho_liq + (1 - C_L) * rho_g  # No-slip density
            rho_s = H_L * rho_liq + (1 - H_L) * rho_g  # In-situ density
            mu_ns = C_L * mu_liq + (1 - C_L) * props["gas_viscosity"]  # No-slip viscosity
            
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m
            
            # Calculate effective roughness with Gray's correction
            k0 = 28.5 * sigma_lbf_ft / (rho_ns * v_m**2)
            k_eff = max(roughness_rel + k0, 2.77e-5)
            
            # Calculate Reynolds number
            Re = (rho_ns * v_m * D) / (mu_ns + 1e-10)
            self.reynolds_numbers[i] = Re
            
            # Calculate friction factor with effective roughness
            if Re > 2100:
                f_D = (-1.8 * math.log10(((k_eff/3.7)**1.11) + (6.9/Re)))**-2
            else:
                f_D = 64.0 / Re
            self.friction_factors[i] = f_D
            
            # Pressure gradient components
            # Hydrostatic component (psi/ft) - adjusted for inclination
            self.dpdz_elevation[i] = rho_s * self.G * math.cos(inclination_rad) / (144.0 * self.G_C)
            
            # Friction component (psi/ft)
            self.dpdz_friction[i] = f_D * rho_ns * v_m**2 / (2.0 * self.G_C * D * 144.0)
            
            # Acceleration component (psi/ft) - neglected in Gray
            self.dpdz_acceleration[i] = 0.0
            
            # Total pressure gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i]
            
            # Calculate next pressure
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = p + self.dpdz_total[i] * dz

def calculate_gray(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile using the Gray correlation
    """
    correlation = Gray(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()
