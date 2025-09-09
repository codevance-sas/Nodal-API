from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsResult, HydraulicsInput
from app.services.pvt.gas_props import calculate_z as calculate_z_factor, calculate_bg

class HagedornBrown(CorrelationBase):
    def __init__(self, data):
        super().__init__(data)
        self.method_name = "Hagedorn-Brown (Pure)"

                # --- START GAS LIFT MODIFICATION ---
        # Store gas lift configuration from the input data
        self.gas_lift_config = data.gas_lift
        self.gas_lift_enabled = self.gas_lift_config and self.gas_lift_config.enabled
        if self.gas_lift_enabled:
            self.gas_lift_depth = self.gas_lift_config.injection_depth
            # Convert from MCFD (frontend input) to SCFD for internal calculations
            self.gas_lift_volume_scfd = self.gas_lift_config.injection_volume_mcfd * 1000
            self.injected_gas_gravity = self.gas_lift_config.injected_gas_gravity

    def calculate_pressure_profile(self):
        for i in range(self.depth_steps - 1):
            p = self.pressures[i]
            T = self.temperatures[i] 
            T_rankine = T + 459.67
            depth = self.depth_points[i]
            segment = self._calculate_pipe_segment(depth)
            D = segment.diameter / 12
            A = self.PI * (D/2)**2
            roughness_rel = self.wellbore.roughness / (segment.diameter * 12)

            props = self._calculate_fluid_properties(p, T)

            Qo, Qw, Qg_reservoir_acfd = self._convert_production_rates(props)

            # --- START GAS LIFT LOGIC ---
            Qg_total_acfd = Qg_reservoir_acfd

            if self.gas_lift_enabled and depth <= self.gas_lift_depth and self.gas_lift_volume_scfd > 0:
                # 1. Convert injected gas from SCFD to ACFS (actual ft³/s)
                # First, get Bg for the *injected gas* at current P, T
                # Create a temporary PVTInput-like object for the injected gas
                injected_gas_data = {
                    "pressure": p,
                    "temperature": T_rankine,
                    "gas_gravity": self.injected_gas_gravity
                }
                
                z_injected = calculate_z_factor(type('obj', (object,), injected_gas_data)())
                bg_injected = calculate_bg(type('obj', (object,), injected_gas_data)(), z_injected) # bg is in ft³/scf

                # 2. Convert standard volume to actual volume rate (SCFD already converted from MCFD)
                injected_gas_acfd = self.gas_lift_volume_scfd * bg_injected # Actual ft³ per day

                # 3. Add to the total gas rate
                Qg_total_acfd += injected_gas_acfd

            v_sl, v_sg, v_m = self._calculate_superficial_velocities(Qo, Qw, Qg_total_acfd, A)
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
