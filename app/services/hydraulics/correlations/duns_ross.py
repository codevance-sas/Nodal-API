import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput

class DunsRoss(CorrelationBase):
    """
    Refined implementation of the Duns & Ros vertical multiphase flow correlation.
    Excludes placeholder acceleration term and improves sampling and transition modeling.
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Duns-Ross"
        self.survey_data = data.survey_data
        if self.survey_data:
            self.survey_data.sort(key=lambda s: s.md)

    def calculate_pressure_profile(self):
        for i in range(self.depth_steps - 1):
            p = self.pressures[i]
            T = self.temperatures[i]
            depth = self.depth_points[i]
            
            # Find the correct pipe and survey segment for the current depth
            pipe_segment = self._calculate_pipe_segment(depth)
            survey_segment = self._calculate_survey_segment(depth) if self.survey_data else None
            
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
            
            # Calculate surface tension using helper method
            sigma, sigma_lbf_ft = self._calculate_surface_tension(p, T)
            
            # Calculate dimensionless numbers for flow pattern determination
            N_gv = v_sg * math.sqrt(rho_g / (self.G * sigma_lbf_ft))
            N_lv = v_sl * math.sqrt(rho_g / (self.G * sigma_lbf_ft))
            N_d = D * math.sqrt((rho_liq - rho_g) * self.G / sigma_lbf_ft)
            
            # Flow pattern boundaries
            L1 = 0.13 * N_d**0.5
            L2 = 0.24 * N_d**0.5
            L_s = 50 + 36 * N_lv
            L_m = 75 + 84 * N_lv**0.75
            
            # Determine flow regime
            if N_gv <= (L1 + L2 * N_lv):
                regime = "Bubble"
            elif N_gv <= L_s:
                regime = "Slug"
            elif N_gv < L_m:
                regime = "Churn"
            else:
                regime = "Annular"
                
            # Set flow pattern using helper method
            self._set_flow_pattern(i, regime)
            
            # Calculate liquid holdup based on flow regime
            if regime == "Bubble":
                v_b = 0.24
                H_L = 1.0 - 0.5 * (v_sg / (v_b + v_m))
            elif regime == "Slug":
                F1 = 0.0246 * N_d**0.5
                F2 = 1.0 / (0.0726 + 0.4257 * N_lv - 0.05747 * N_lv**2)
                F3 = 1.0 / (1.0 + F1 * (N_gv / (N_lv + 0.001))**F2)
                H_L = F3 * (1.0 - v_sg / v_m)
            elif regime == "Churn":
                H_L_slug = 0.5 * (1.0 - v_sg / v_m)
                H_L_ann = C_L
                t = (N_gv - L_s) / (L_m - L_s)
                H_L = H_L_slug * (1 - t) + H_L_ann * t
            else:
                H_L = 0.8 * C_L + 0.2 * (1.0 - v_sg / v_m)
            
            # Ensure holdup is within reasonable bounds
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L
            
            # Calculate mixture properties
            rho_s = H_L * rho_liq + (1 - H_L) * rho_g
            rho_ns = C_L * rho_liq + (1 - C_L) * rho_g
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m
            
            # Calculate Reynolds number based on flow regime
            if regime in ["Bubble", "Slug", "Churn"]:
                Re = (rho_liq * v_m * D) / mu_liq
            else:
                k_eff = roughness_rel + 0.005 * H_L
                Re = (rho_g * v_m * D) / props["gas_viscosity"]
            self.reynolds_numbers[i] = Re
            
            # Calculate friction factor
            self.friction_factors[i] = self._calculate_friction_factor(Re, roughness_rel)
            
            # Calculate pressure gradient components using helper methods
            self.dpdz_elevation[i] = self._calculate_elevation_gradient(rho_s, inclination_rad)
            self.dpdz_friction[i] = self._calculate_friction_gradient(self.friction_factors[i], rho_ns, v_m, D)
            self.dpdz_acceleration[i] = 0.0  # Neglected in this implementation
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i]
            
            # Update pressure for next depth point
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = self.pressures[i] + self.dpdz_total[i] * dz

    def _calculate_survey_segment(self, depth: float):
        if not self.survey_data:
            return None
        for i in range(len(self.survey_data) - 1):
            if self.survey_data[i].md <= depth < self.survey_data[i+1].md:
                return self.survey_data[i]
        return self.survey_data[-1]

def calculate_duns_ross(data: HydraulicsInput) -> HydraulicsResult:
    correlation = DunsRoss(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()