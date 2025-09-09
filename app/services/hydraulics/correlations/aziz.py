import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class Aziz(CorrelationBase):
    """
    Implementation of Aziz et al. correlation for two-phase flow
    focusing on bubble and slug flow patterns
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Aziz et al."
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
        Calculate pressure profile using the Aziz et al. correlation
        focusing on bubble and slug flow patterns
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
            Qg = self._calculate_gas_prod_rate_gas_lift(depth, p, T, Qg)
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
            
            # Aziz et al. flow regime determination (primarily focused on bubble/slug)
            # Critical gas velocity for transition
            v_crit = 0.3 * (C_L**0.5) * (1.0 + 0.2 * abs(math.sin(inclination_rad)))
            
            # Flow pattern determination
            if v_sg < v_crit:
                regime = "Bubble"
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE
            elif v_sg < 10.0:  # Arbitrary high limit
                regime = "Slug"
                self.flow_patterns[i] = FlowPatternEnum.SLUG
            else:
                regime = "Annular"
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR
                
            # Holdup calculation using drift-flux approach (Aziz focuses on this)
            if regime == "Bubble":
                # Discrete bubbles in liquid at any inclination
                # Use drift-flux model (distribution parameter and drift velocity)
                C0 = 1.13 + 0.2 * abs(math.sin(inclination_rad))  # Higher in inclined pipes
                V_d = 0.5 * math.sqrt(self.G * D)  # Drift velocity for bubbles
                alpha = (C0 * v_sg + V_d * math.cos(inclination_rad)) / (v_m + 1e-9)  # Gas void fraction
                alpha = min(max(alpha, 0.0), 0.95)  # Keep in reasonable range
                H_L = 1.0 - alpha
            elif regime == "Slug":
                # Taylor bubbles present
                C0 = 1.2  # Higher distribution parameter for slug
                V_d = 0.35 * math.sqrt(self.G * D)  # Drift velocity for larger bubbles
                alpha = (C0 * v_sg + V_d * math.cos(inclination_rad)) / (v_m + 1e-9)
                alpha = min(max(alpha, 0.0), 0.95)
                H_L = 1.0 - alpha
            else:  # Annular - beyond main focus of Aziz
                # Assume low holdup in annular
                H_L = 0.9 * C_L  # Slight slip
                
            # Ensure holdup is within physical limits
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Mixture properties
            # Actual mixture density
            rho_s = H_L * rho_liq + (1.0 - H_L) * rho_g
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m
            
            # Approximate mixture viscosity
            mu_m = H_L * mu_liq + (1.0 - H_L) * props["gas_viscosity"]
            
            # Friction calculations
            # Aziz generally uses mixture properties for friction
            Re_m = (rho_s * v_m * D) / (mu_m + 1e-10)
            self.reynolds_numbers[i] = Re_m
            
            # Calculate friction factor
            self.friction_factors[i] = self._calculate_friction_factor(Re_m, roughness_rel)
            
            # Pressure gradient components
            # Hydrostatic component (psi/ft) - adjusted for inclination
            self.dpdz_elevation[i] = rho_s * self.G * math.cos(inclination_rad) / (144.0 * self.G_C)
            
            # Friction component (psi/ft)
            self.dpdz_friction[i] = self.friction_factors[i] * rho_s * v_m**2 / (2.0 * self.G_C * D * 144.0)
            
            # Acceleration component (psi/ft)
            # Simplified - in full implementation would depend on gas expansion
            self.dpdz_acceleration[i] = 0.0
            if i > 0 and self.pressures[i] > 0 and self.pressures[i-1] > 0:
                # Simple approximation based on pressure change
                gas_expansion = self.pressures[i-1] / self.pressures[i]
                if gas_expansion > 1.01:  # Only include if significant expansion
                    self.dpdz_acceleration[i] = 0.05 * self.dpdz_friction[i]  # Simplified approximation
                    
            # Total pressure gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i] + self.dpdz_acceleration[i]
            
            # Calculate next pressure
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = p + self.dpdz_total[i] * dz

def calculate_aziz(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile using the Aziz et al. correlation
    focusing on bubble and slug flow patterns
    """
    correlation = Aziz(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()