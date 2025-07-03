from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput
import math

class HagedornBrown(CorrelationBase):
    def __init__(self, data):
        super().__init__(data)
        self.method_name = "Hagedorn-Brown (Pure)"

    def calculate_pressure_profile(self):
        for i in range(self.depth_steps - 1):
            p = self.pressures[i]
            T = self.temperatures[i]
            depth = self.depth_points[i]
            segment = self._calculate_pipe_segment(depth)
            D = segment.diameter / 12
            A = self.PI * (D/2)**2
            roughness_rel = self.wellbore.roughness / (segment.diameter * 12)

            props = self._calculate_fluid_properties(p, T)
            Qo, Qw, Qg = self._convert_production_rates(props)
            v_sl, v_sg, v_m = self._calculate_superficial_velocities(Qo, Qw, Qg, A)
            self.v_sl_profile[i] = v_sl
            self.v_sg_profile[i] = v_sg

            rho_o, rho_w, rho_g = self._calculate_fluid_densities(props)
            rho_liq, mu_liq = self._calculate_liquid_properties(rho_o, rho_w, props)

            psi = (30.0 - 0.1 * (T - 60) - 0.005 * (p - 14.7))
            psi = max(1.0, psi)
            psi = (psi / (self.G_C * (rho_liq - rho_g) * D))**0.25

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

            self.holdups[i] = max(0.01, min(0.99, H_L))

            if self.holdups[i] > 0.8:
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE
            elif self.holdups[i] > 0.3:
                self.flow_patterns[i] = FlowPatternEnum.SLUG
            elif self.holdups[i] > 0.1:
                self.flow_patterns[i] = FlowPatternEnum.TRANSITION
            else:
                self.flow_patterns[i] = FlowPatternEnum.ANNULAR

            rho_s = self.holdups[i] * rho_liq + (1 - self.holdups[i]) * rho_g
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m

            mu_m = mu_liq**self.holdups[i] * props["gas_viscosity"]**(1 - self.holdups[i])
            Re = (rho_s * v_m * D) / (mu_m + 1e-10)
            self.reynolds_numbers[i] = Re

            self.friction_factors[i] = self._calculate_friction_factor(Re, roughness_rel)

            self.dpdz_elevation[i] = rho_s * self.G / (144.0 * self.G_C)
            self.dpdz_friction[i] = self.friction_factors[i] * rho_s * v_m**2 / (2 * self.G_C * D * 144.0)
            self.dpdz_total[i] = self.dpdz_elevation[i] + self.dpdz_friction[i]

            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = self.pressures[i] + self.dpdz_total[i] * dz

def calculate_hagedorn_brown(data: HydraulicsInput) -> HydraulicsResult:
    correlation = HagedornBrown(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()
