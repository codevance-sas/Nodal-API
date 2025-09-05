import math
import numpy as np
from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsInput, HydraulicsResult
from app.services.pvt.gas_props import calculate_z as calculate_z_factor, calculate_bg

class BeggsBrill(CorrelationBase):
    """
    Pure implementation of the Beggs & Brill (1973) multiphase flow correlation.
    This version excludes acceleration pressure drop and uses the original 
    flow regime maps, liquid holdup, and inclination correction as defined by Beggs & Brill.
    """
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Beggs & Brill (Pure)"
        self.survey_data = data.survey_data
        if self.survey_data:
            self.survey_data.sort(key=lambda s: s.md)

        # --- START GAS LIFT MODIFICATION ---
        # Store gas lift configuration from the input data
        self.gas_lift_config = data.gas_lift
        self.gas_lift_enabled = self.gas_lift_config and self.gas_lift_config.enabled
        if self.gas_lift_enabled:
            self.gas_lift_depth = self.gas_lift_config.injection_depth
            self.gas_lift_volume_scfd = self.gas_lift_config.injection_volume_scfd
            self.injected_gas_gravity = self.gas_lift_config.injected_gas_gravity

    def calculate_pressure_profile(self):
        # Stepwise calculation down the wellbore
        for i in range(self.depth_steps - 1):
            p = self.pressures[i]
            T = self.temperatures[i]
            T_rankine = T + 459.67
            depth = self.depth_points[i]

            # Find the correct pipe and survey segment for the current depth
            pipe_segment = self._calculate_pipe_segment(depth)
            survey_segment = self._calculate_survey_segment(depth)
            
            D = pipe_segment.diameter / 12.0  # Convert tubing ID from inches to ft
            A = self.PI * (D / 2.0) ** 2
            roughness_rel = self.wellbore.roughness / pipe_segment.diameter

            # Beggs & Brill angle `theta` is from the horizontal.
            # survey inclination is from vertical. For upward flow, theta = 90 - inclination.
            inclination_rad = math.radians(survey_segment.inclination if survey_segment else self.wellbore.deviation)
            theta_rad = (self.PI / 2.0) - inclination_rad

            # Calculate fluid properties
            props = self._calculate_fluid_properties(p, T)

            Qo, Qw, Qg_reservoir_acfs = self._convert_production_rates(props)

            # --- START GAS LIFT LOGIC ---
            Qg_total_acfs = Qg_reservoir_acfs

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

                # 2. Convert standard volume to actual volume rate
                injected_gas_scfs = self.gas_lift_volume_scfd / 86400.0 # SCF per second
                injected_gas_acfs = injected_gas_scfs * bg_injected # Actual ft³ per second

                # 3. Add to the total gas rate
                Qg_total_acfs += injected_gas_acfs

            v_sl, v_sg, v_m = self._calculate_superficial_velocities(Qo, Qw, Qg_total_acfs, A)
            self.v_sl_profile[i] = v_sl
            self.v_sg_profile[i] = v_sg

            # No-slip liquid content (input liquid fraction C_L)
            C_L = v_sl / v_m if v_m > 0 else 0.0

            # Fluid densities and liquid properties
            rho_o, rho_w, rho_g = self._calculate_fluid_densities(props)
            rho_liq, mu_liq = self._calculate_liquid_properties(rho_o, rho_w, props)
            
            # Approximate surface tension (sigma)
            sigma = self._calculate_surface_tension(p, T, rho_o, rho_w)

            # --- Beggs & Brill Correlation Calculations ---
            # 1. Dimensionless numbers
            N_Fr = v_m**2 / (self.G * D)  # Froude number
            N_LV = 1.938 * v_sl * ((rho_liq / (self.G * sigma)) ** 0.25) if sigma > 0 else 0

            # 2. Flow pattern map boundaries
            L1 = 316.0 * (C_L ** 0.302)
            L2 = 0.0009252 * (C_L ** -2.4684) if C_L > 0 else float('inf')
            L3 = 0.10 * (C_L ** -1.4516) if C_L > 0 else float('inf')
            L4 = 0.50 * (C_L ** -6.738) if C_L > 0 else float('inf')

            # 3. Determine flow regime for horizontal flow
            if ((C_L < 0.01) and (N_Fr < L1)) or ((C_L >= 0.01) and (N_Fr < L2)):
                flow_regime = "Segregated"
                self.flow_patterns[i] = FlowPatternEnum.STRATIFIED
            elif ((0.01 <= C_L < 0.4) and (L3 < N_Fr <= L1)) or ((C_L >= 0.4) and (L3 < N_Fr <= L4)):
                flow_regime = "Intermittent"
                self.flow_patterns[i] = FlowPatternEnum.SLUG
            elif (N_Fr > L4) or ((C_L < 0.4) and (N_Fr >= L4) and (L3 < N_Fr)):
                flow_regime = "Distributed"
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE
            elif (L2 <= N_Fr < L3):
                flow_regime = "Transition"
                self.flow_patterns[i] = FlowPatternEnum.TRANSITION
            else:
                flow_regime = "Distributed"
                self.flow_patterns[i] = FlowPatternEnum.BUBBLE

            # 4. Liquid holdup for horizontal flow (H_L0)
            H_L0 = self._calculate_horizontal_holdup(flow_regime, C_L, N_Fr, L2, L3)
            H_L0 = max(H_L0, C_L)

            # 5. Inclination correction factor B(θ)
            B_theta = self._calculate_inclination_correction(flow_regime, C_L, N_LV, N_Fr, theta_rad)

            # 6. Liquid holdup at actual inclination
            H_L = H_L0 * B_theta
            self.holdups[i] = max(0.01, min(0.99, H_L))

            # 7. Mixture properties
            rho_ns = C_L * rho_liq + (1.0 - C_L) * rho_g  # No-slip density
            rho_s = self.holdups[i] * rho_liq + (1.0 - self.holdups[i]) * rho_g  # In-situ density
            self.mixture_densities[i] = rho_s
            self.mixture_velocities[i] = v_m

            # --- Pressure gradient components (psi/ft) ---
            # (a) Elevation gradient
            self.dpdz_elevation[i] = rho_s * self.G * math.sin(theta_rad) / (144.0 * self.G_C)

            # (b) Frictional gradient
            mu_ns = C_L * mu_liq + (1.0 - C_L) * props["gas_viscosity"]
            Re_ns = (rho_ns * v_m * D) / (mu_ns + 1e-10)
            self.reynolds_numbers[i] = Re_ns
            f_ns = self._calculate_friction_factor(Re_ns, roughness_rel)
            f_tp = self._calculate_two_phase_friction_factor(f_ns, C_L, self.holdups[i])
            self.friction_factors[i] = f_tp
            self.dpdz_friction[i] = f_tp * (rho_ns * v_m**2) / (2.0 * self.G_C * D * 144.0)

            # (c) Acceleration gradient
            e_k = (rho_s * v_m * v_sg) / (self.G_C * p * 144.0)
            self.dpdz_acceleration[i] = e_k

            # Total gradient and pressure update
            self.dpdz_total[i] = (self.dpdz_elevation[i] + self.dpdz_friction[i]) / (1.0 - e_k)
            dz = self.depth_points[i+1] - self.depth_points[i]
            self.pressures[i+1] = self.pressures[i] + self.dpdz_total[i] * dz

    def _calculate_survey_segment(self, depth: float):
        if not self.survey_data:
            return None
        for i in range(len(self.survey_data) - 1):
            if self.survey_data[i].md <= depth < self.survey_data[i+1].md:
                return self.survey_data[i]
        return self.survey_data[-1]

    def _calculate_surface_tension(self, p, T, rho_o, rho_w):
        # Using a simplified correlation for oil-gas and water-gas surface tension
        sigma_oil_gas = max(1.0, 30.0 - 0.1 * (T - 60.0) - 0.005 * (p - 14.7))
        sigma_water_gas = max(5.0, 70.0 - 0.15 * (T - 60.0) - 0.01 * (p - 14.7))
        
        total_liquid_rate = self.fluid.oil_rate + self.fluid.water_rate
        if total_liquid_rate > 0:
            oil_frac = self.fluid.oil_rate / total_liquid_rate
            water_frac = self.fluid.water_rate / total_liquid_rate
            return oil_frac * sigma_oil_gas + water_frac * sigma_water_gas
        return sigma_oil_gas # Default to oil-gas if no liquid

    def _calculate_horizontal_holdup(self, flow_regime, C_L, N_Fr, L2, L3):
        reg_params = {
            "Segregated":  (0.98,  0.4846, 0.0868),
            "Intermittent": (0.845, 0.5351, 0.0173),
            "Distributed": (1.065, 0.5824, 0.0609)
        }
        if flow_regime == "Transition":
            a_seg, b_seg, c_seg = reg_params["Segregated"]
            a_int, b_int, c_int = reg_params["Intermittent"]
            H_L0_seg = a_seg * (C_L ** b_seg) / (N_Fr ** c_seg) if N_Fr > 0 else 1.0
            H_L0_int = a_int * (C_L ** b_int) / (N_Fr ** c_int) if N_Fr > 0 else 1.0
            A = (L3 - N_Fr) / (L3 - L2) if (L3 != L2) else 0.5
            return A * H_L0_seg + (1.0 - A) * H_L0_int
        else:
            a, b, c = reg_params.get(flow_regime, reg_params["Distributed"])
            return a * (C_L ** b) / (N_Fr ** c) if N_Fr > 0 else 1.0

    def _calculate_inclination_correction(self, flow_regime, C_L, N_LV, N_Fr, theta_rad):
        beta = 0.0
        if theta_rad > 1e-6:  # Uphill flow
            params = {
                "Segregated":  (0.011, -3.768, 3.539, -1.614),
                "Intermittent": (2.96, 0.305, -0.4473, 0.0978),
            }.get(flow_regime)
            if params:
                D, e, f, g_coeff = params
                term = D * (C_L ** e) * (N_LV ** f) * (N_Fr ** g_coeff)
                if term > 0: beta = (1.0 - C_L) * math.log(term)
        elif theta_rad < -1e-6:  # Downhill flow
            D, e, f, g_coeff = 4.7, -0.3692, 0.1244, -0.5056
            term = D * (C_L ** e) * (N_LV ** f) * (N_Fr ** g_coeff)
            if term > 0: beta = (1.0 - C_L) * math.log(term)
        
        beta = max(0.0, beta)
        return 1.0 + beta * (math.sin(1.8 * theta_rad) - (1.0/3.0) * (math.sin(1.8 * theta_rad) ** 3))

    def _calculate_two_phase_friction_factor(self, f_ns, C_L, H_L):
        y = C_L / (H_L ** 2 + 1e-9)
        if y <= 1.0 or y > 1.2:
            ln_y = math.log(y + 1e-9)
            s = ln_y / (-0.0523 + 3.182 * ln_y - 0.8725 * (ln_y ** 2) + 0.01853 * (ln_y ** 4))
        else:
            s = math.log(2.2 * y - 1.2)
        return f_ns * math.exp(s)

def calculate_beggs_brill(data: HydraulicsInput) -> HydraulicsResult:
    correlation = BeggsBrill(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()