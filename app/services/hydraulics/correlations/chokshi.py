
import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class Chokshi(CorrelationBase):
    """
    Implementation of Chokshi mechanistic model for multiphase flow
    with flow pattern prediction and pressure drop calculation
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Chokshi"
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
        Calculate pressure profile using the Chokshi mechanistic model
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
            
            # Chokshi flow pattern prediction
            # Calculate dimensionless parameters for flow pattern map
            N_lv = v_sl * (rho_liq / (self.G * sigma_lbf_ft))**0.25  # Liquid velocity number
            N_gv = v_sg * (rho_liq / (self.G * sigma_lbf_ft))**0.25  # Gas velocity number
            Fr_m = v_m**2 / (self.G * D)  # Mixture Froude number
            
            # Flow pattern determination based on Chokshi criteria
            if v_sg < 0.2:  # Very low gas velocity
                regime = "Dispersed Bubble"
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE
            elif Fr_m < 0.3:  # Low Froude number
                if v_sl > 0.1:  # Some liquid present
                    regime = "Slug"
                    self.flow_patterns[i] = FlowPatternEnum.SLUG
                else:  # Very little liquid
                    regime = "Stratified"
                    self.flow_patterns[i] = FlowPatternEnum.STRATIFIED
            elif N_gv < 1.0:
                regime = "Slug"
                self.flow_patterns[i] = FlowPatternEnum.SLUG
            elif N_gv < 3.0:
                regime = "Churn"
                self.flow_patterns[i] = FlowPatternEnum.TRANSITION
            else:
                regime = "Annular"
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR
                
            # Compute holdup via mechanistic model
            if regime == "Dispersed Bubble":
                # Gas bubbles well-dispersed in liquid (like homogeneous flow)
                # For dispersed bubble, use drift-flux with small drift velocity
                C0 = 1.0  # Distribution parameter
                v_d = 0.05  # Small drift velocity for tiny bubbles
                alpha = (v_sg + v_d) / (v_m + v_d)  # Gas void fraction
                alpha = min(max(alpha, 0.0), 0.25)  # Limit for dispersed bubble
                H_L = 1.0 - alpha
            elif regime in ["Slug", "Stratified"]:
                # Large Taylor bubbles and liquid slugs or stratified layers
                # For slug, use drift-flux model for Taylor bubble rise
                v_d = 0.35 * np.sqrt(self.G * D)  # Drift velocity
                C0 = 1.2  # Distribution parameter
                alpha = (C0 * v_sg + v_d) / (v_m + 1e-9)  # Gas void fraction
                alpha = min(max(alpha, 0.0), 0.85)
                H_L = 1.0 - alpha
            elif regime == "Churn":
                # Churn (flooded slug) - more chaotic
                # Use drift-flux with lower C0
                C0 = 1.0
                v_d = 0.4 * np.sqrt(self.G * D)
                alpha = (C0 * v_sg + v_d) / (v_m + 1e-9)
                alpha = min(max(alpha, 0.0), 0.9)
                H_L = 1.0 - alpha
            elif regime == "Annular":
                # Annular flow: gas core, liquid film
                # Solve for film thickness - simplified approach
                # Estimate entrainment fraction
                entrainment = 0.3 + 0.5 * v_sg / (v_sg + v_sl + 1.0)
                entrainment = min(0.9, entrainment)
                
                # Film thickness calculation (simplified)
                # Assume liquid film occupies a small fraction of area
                delta = 0.01 * D * (v_sl / (v_sg + 0.1))**0.5
                
                # Calculate holdup from film thickness
                H_L = 4.0 * delta / D - 4.0 * (delta / D)**2
                
                # Adjust for liquid entrainment in gas core
                H_L = (1.0 - entrainment) * H_L + entrainment * C_L
                
            # Ensure holdup is within physical limits
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Mixture properties
            # Actual mixture density
            rho_m = H_L * rho_liq + (1.0 - H_L) * rho_g
            self.mixture_densities[i] = rho_m
            self.mixture_velocities[i] = v_m
            
            # Friction factor calculation
            if regime in ["Dispersed Bubble", "Slug", "Churn"]:
                # Liquid wets the pipe; use liquid-wall friction
                Re_L = (rho_liq * v_sl * D) / (mu_liq + 1e-10)
                
                # For highly viscous mixtures, use mixture properties
                if mu_liq > 10.0:  # High viscosity liquid
                    Re_L = (rho_m * v_m * D) / ((H_L * mu_liq + (1.0 - H_L) * props["gas_viscosity"]) + 1e-10)
                    
                self.reynolds_numbers[i] = Re_L
                self.friction_factors[i] = self._calculate_friction_factor(Re_L, roughness_rel)
            elif regime == "Annular":
                # Gas-core dominated; use gas-phase friction with modified roughness
                d_eff = D * (1.0 - 2.0 * delta / D)  # Effective diameter
                Re_G = (rho_g * v_sg * d_eff) / (props["gas_viscosity"] + 1e-10)
                self.reynolds_numbers[i] = Re_G
                
                # Add roughness for liquid film
                effective_roughness = roughness_rel + delta / D
                self.friction_factors[i] = self._calculate_friction_factor(Re_G, effective_roughness)
            else:
                # Default case
                Re = (rho_m * v_m * D) / ((H_L * mu_liq + (1.0 - H_L) * props["gas_viscosity"]) + 1e-10)
                self.reynolds_numbers[i] = Re
                self.friction_factors[i] = self._calculate_friction_factor(Re, roughness_rel)
            
            # Pressure gradient components
            # Hydrostatic component (psi/ft) - adjusted for inclination
            self.dpdz_elevation[i] = rho_m * self.G * math.cos(inclination_rad) / (144.0 * self.G_C)
            
            # Friction component (psi/ft)
            self.dpdz_friction[i] = self.friction_factors[i] * (rho_m * v_m**2) / (2.0 * self.G_C * D * 144.0)
            
            # Acceleration component (psi/ft)
            # Include gas expansion effects
            if i > 0 and self.pressures[i] > 0 and self.pressures[i-1] > 0:
                # Simple approximation
                gas_velocity_change = v_sg * (self.pressures[i-1] / self.pressures[i] - 1.0)
                self.dpdz_acceleration[i] = (rho_m * v_m * gas_velocity_change) / (self.G_C * 144.0 * (self.depth_points[i] - self.depth_points[i-1]))
            else:
                self.dpdz_acceleration[i] = 0.0
                
            # Total pressure gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i] + self.dpdz_acceleration[i]
            
            # Calculate next pressure
            # Using the step size
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = p + self.dpdz_total[i] * dz

def calculate_chokshi(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile using the Chokshi mechanistic model
    """
    correlation = Chokshi(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()
