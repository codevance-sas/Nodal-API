import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class HasanKabir(CorrelationBase):
    """
    Implementation of Hasan-Kabir correlation for multiphase flow
    with consideration of pipe roughness effects
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Hasan-Kabir"
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
        Calculate pressure profile using the Hasan-Kabir correlation
        with consideration of pipe roughness effects
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
            
            # Hasan-Kabir flow pattern identification
            # Use their criteria for boundaries based on superficial velocities
            
            # Boundary equations (simplified from Hasan-Kabir)
            # Boundary A (bubbly to slug/churn)
            boundary_A = 0.429 * v_sl + 0.357 * v_sl * abs(math.sin(inclination_rad))
            
            # Boundary C (slug to dispersed bubble) - simplified
            boundary_C = 1.083 * v_sl + 0.52 * math.sqrt(self.G * (rho_liq - rho_g) / rho_g)
            
            # Flow pattern determination
            if v_sg < boundary_A:
                if v_sl < 1.0:  # Low liquid rate
                    regime = "Bubbly"
                    self.flow_patterns[i] = FlowPatternEnum.BUBBLE
                else:  # Higher liquid rate
                    regime = "Slug/Churn"
                    self.flow_patterns[i] = FlowPatternEnum.SLUG
            elif v_sg < boundary_C:
                regime = "Dispersed Bubble"
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE
            else:
                regime = "Annular"
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR
                
            # Liquid holdup based on regime
            if regime == "Bubbly":
                # Bubbly flow: discrete bubbles, continuous liquid
                # Hasan-Kabir uses drift-flux with their coefficients
                C0 = 1.15  # Distribution parameter
                V_d = 0.0   # Small bubbles assumed carried with liquid
                alpha = (C0 * v_sg) / (v_m + 1e-9)
                alpha = min(max(alpha, 0.0), 0.95)
                H_L = 1.0 - alpha
            elif regime == "Slug/Churn":
                # Slug or churn flow: larger gas pockets
                # Use drift velocity for Taylor bubbles
                C0 = 1.2
                # Simplified form of Hasan-Kabir's drift velocity
                V_d = 1.53 * ((self.G * (rho_liq - rho_g) * sigma_lbf_ft**2) / (rho_liq**2))**0.25
                alpha = (C0 * v_sg + V_d) / (v_m + 1e-9)
                alpha = min(max(alpha, 0.0), 0.95)
                H_L = 1.0 - alpha
            elif regime == "Dispersed Bubble":
                # Dispersed bubble: high gas fraction, gas pockets broken up
                C0 = 1.0
                V_d = 0.0
                alpha = C0 * v_sg / (v_m + 1e-9)
                alpha = min(max(alpha, 0.0), 0.9)
                H_L = 1.0 - alpha
            else:  # Annular
                # Annular: gas core, liquid film
                H_L = 0.9 * C_L  # Slight slip
                
            # Ensure holdup is within physical limits
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Mixture properties
            # In Hasan-Kabir, mixture density is calculated based on in-situ volume fractions
            rho_m = H_L * rho_liq + (1.0 - H_L) * rho_g
            self.mixture_densities[i] = rho_m
            self.mixture_velocities[i] = v_m
            
            # Approximate mixture viscosity
            mu_m = H_L * mu_liq + (1.0 - H_L) * props["gas_viscosity"]
            
            # Reynolds number using mixture properties
            Re_m = (rho_m * v_m * D) / (mu_m + 1e-10)
            self.reynolds_numbers[i] = Re_m
            
            # Hasan-Kabir is especially concerned with pipe roughness effects
            # Adjust effective roughness based on flow regime and actual roughness
            if roughness_rel > 0.001:  # Rougher than normal
                # Calculate roughness factor based on actual pipe roughness
                roughness_factor = 1.0 + (roughness_rel - 0.0006) / 0.0004
                effective_roughness = roughness_rel * roughness_factor
            else:
                effective_roughness = roughness_rel
                
            # Further adjust based on flow regime
            if regime in ["Bubbly", "Dispersed Bubble"]:
                # Liquid continuous phase - less sensitive to roughness
                effective_roughness *= 0.9
            elif regime == "Annular":
                # Gas continuous with liquid film - more sensitive
                effective_roughness *= 1.2
                
            # Friction factor calculation - using modified roughness
            if Re_m > 2100:
                # Turbulent flow
                f_D = (-1.8 * math.log10(((effective_roughness/3.7)**1.11) + (6.9/Re_m)))**(-2)
            else:
                # Laminar flow
                f_D = 64.0 / Re_m
                
            self.friction_factors[i] = f_D
            
            # Pressure gradient components
            # Hydrostatic component (psi/ft) - adjusted for inclination
            self.dpdz_elevation[i] = rho_m * self.G * math.cos(inclination_rad) / (144.0 * self.G_C)
            
            # Friction component (psi/ft)
            self.dpdz_friction[i] = f_D * (rho_m * v_m**2) / (2.0 * self.G_C * D * 144.0)
            
            # Acceleration component - typically small
            self.dpdz_acceleration[i] = 0.0
            
            # Total pressure gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i] + self.dpdz_acceleration[i]
            
            # Calculate next pressure
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = p + self.dpdz_total[i] * dz

def calculate_hasan_kabir(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile using the Hasan-Kabir correlation
    with consideration of pipe roughness effects
    """
    correlation = HasanKabir(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()