import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class MukherjeeBrill(CorrelationBase):
    """
    Implementation of Mukherjee-Brill correlation
    Specialized for directional (deviated) wells
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Mukherjee-Brill"
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
        Calculate pressure profile using the Mukherjee-Brill correlation
        Specialized for directional (deviated) wells
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
            # For Mukherjee-Brill, we need the angle from horizontal (theta)
            inclination_rad = math.radians(survey_segment.inclination if survey_segment else self.wellbore.deviation)
            theta = (self.PI / 2.0) - inclination_rad  # Convert from vertical to horizontal reference
            downward = theta < 0  # Downward flow check
            
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
            
            # Dimensionless parameters for flow pattern identification
            N_Fr = v_m**2 / (self.G * D)  # Froude number
            N_LV = 1.938 * v_sl * ((rho_liq / (self.G * sigma_lbf_ft))**0.25)  # Liquid velocity number
            
            # Transition velocities - simplified from Mukherjee-Brill
            v_transition_A = 0.5 + 0.1 * abs(math.sin(theta))  # Bubble/Slug transition
            v_transition_stratified = 0.3 * math.sqrt(D)  # Stratified transition (for downhill)
            v_transition_C = 8.0 - 3.0 * abs(math.sin(theta))  # Slug/Annular transition
            
            # Flow pattern determination
            if v_sg < v_transition_A:
                if v_sl > 0.3:  # Higher liquid velocity favors bubble
                    regime = "Bubble/Slug"
                    self.flow_patterns[i] = FlowPatternEnum.BUBBLE
                else:
                    regime = "Bubble/Slug"
                    self.flow_patterns[i] = FlowPatternEnum.SLUG
            elif downward and v_sg < v_transition_stratified:
                regime = "Stratified (Downhill)"
                self.flow_patterns[i] = FlowPatternEnum.STRATIFIED
            elif v_sg < v_transition_C:
                regime = "Slug/Churn"
                self.flow_patterns[i] = FlowPatternEnum.TRANSITION
            else:
                regime = "Annular"
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR
            
            # Liquid holdup calculation
            if regime == "Bubble/Slug":
                # In dispersed bubble or slug, start with no-slip holdup
                H_L0 = C_L
                # Apply Palmer correction for uphill flow
                if theta > 0:
                    # Slight reduction for uphill (Palmer correction)
                    H_L = 0.918 * H_L0
                else:
                    H_L = H_L0
            elif regime == "Stratified (Downhill)":
                # Stratified flow (downhill): liquid in bottom, gas on top.
                # Simplified stratified holdup calculation
                H_L = 0.5 * (1.0 + v_sl / (v_sl + v_sg) - 0.2 * math.sin(-theta))
            elif regime == "Slug/Churn":
                # Slug/Churn: start with no-slip and adjust for inclination
                H_L0 = C_L
                # Inclination correction factor (simplified)
                f_incline = 1.0 - 0.15 * abs(math.sin(theta))
                H_L = H_L0 * f_incline
            else:  # Annular
                # Annular-mist: high gas fraction, liquid as film.
                H_L = 0.9 * C_L  # Assume most liquid entrained with gas (slight slip)
            
            # Ensure holdup is within physical limits
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Calculate mixture properties
            rho_ns = C_L * rho_liq + (1 - C_L) * rho_g  # No-slip density
            rho_s = H_L * rho_liq + (1 - H_L) * rho_g  # In-situ density
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m
            
            # No-slip mixture viscosity (simplified)
            mu_ns = C_L * mu_liq + (1 - C_L) * props["gas_viscosity"]
            
            # Friction factor calculation based on flow regime
            if regime in ["Bubble/Slug", "Slug/Churn"]:
                # Use no-slip Moody friction factor (liquid dominated)
                Re_ns = (rho_ns * v_m * D) / (mu_ns + 1e-10)
                self.reynolds_numbers[i] = Re_ns
                self.friction_factors[i] = self._calculate_friction_factor(Re_ns, roughness_rel)
            elif regime == "Stratified (Downhill)":
                # For stratified, use separate phase friction factors
                Re_L = (rho_liq * v_sl * D) / (mu_liq + 1e-10)
                Re_G = (rho_g * v_sg * D) / (props["gas_viscosity"] + 1e-10)
                self.reynolds_numbers[i] = H_L * Re_L + (1 - H_L) * Re_G
                
                # Calculate friction factors for each phase
                if Re_L > 2100:
                    f_L = (-1.8 * math.log10(((roughness_rel/3.7)**1.11) + (6.9/Re_L)))**(-2)
                else:
                    f_L = 64.0 / Re_L
                    
                if Re_G > 2100:
                    f_G = (-1.8 * math.log10(((roughness_rel/3.7)**1.11) + (6.9/Re_G)))**(-2)
                else:
                    f_G = 64.0 / Re_G
                
                # Combined friction factor (weighted by shear stress areas)
                self.friction_factors[i] = f_L * H_L + f_G * (1 - H_L)
            elif regime == "Annular":
                # Annular flow: use friction factor correlation function of holdup ratio
                phi = H_L / (C_L + 1e-10)  # holdup ratio
                
                # No-slip Reynolds number
                Re_ns = (rho_ns * v_m * D) / (mu_ns + 1e-10)
                self.reynolds_numbers[i] = Re_ns
                
                # Base no-slip friction factor
                f_ns = self._calculate_friction_factor(Re_ns, roughness_rel)
                
                # F(phi) = empirically derived function that increases f with holdup ratio
                # This is a simplified model of the Mukherjee-Brill adjustment
                if phi < 1.0:
                    F_phi = 1.0  # No adjustment for phi < 1
                else:
                    F_phi = phi**0.5  # Increase friction for phi > 1
                    
                self.friction_factors[i] = f_ns * F_phi
            
            # Pressure gradient components
            # Hydrostatic component (psi/ft) - adjusted for inclination
            self.dpdz_elevation[i] = rho_s * self.G * math.sin(theta) / (144.0 * self.G_C)
            
            # Friction component (psi/ft)
            self.dpdz_friction[i] = self.friction_factors[i] * rho_ns * v_m**2 / (2.0 * self.G_C * D * 144.0)
            
            # Acceleration component (psi/ft) - typically small for most conditions
            self.dpdz_acceleration[i] = 0.0
            
            # Total pressure gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i] + self.dpdz_acceleration[i]
            
            # Calculate next pressure
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = p + self.dpdz_total[i] * dz

def calculate_mukherjee_brill(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile using the Mukherjee-Brill correlation
    Specialized for directional (deviated) wells
    """
    correlation = MukherjeeBrill(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()