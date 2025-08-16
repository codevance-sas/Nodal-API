import math
import numpy as np
from typing import List, Optional

from .base import CorrelationBase
from app.schemas.hydraulics import FlowPatternEnum, HydraulicsInput, HydraulicsResult


class BeggsBrill(CorrelationBase):
    """
    Beggs & Brill (1973) multiphase flow correlation with optional gas-lift injection.
    This implementation:
      - Uses original regime maps, horizontal liquid holdup and inclination correction.
      - Treats the acceleration term in a numerically stable way (finite-difference on rho_m * v_m^2).
      - Keeps Fanning friction factor convention consistently (documented below).
      - Adds gas-lift 'hooks' that can be enabled/disabled via HydraulicsInput.gas_lift.

    Assumptions / Conventions:
      * Friction factor is **Fanning** (f_F). If a single-phase friction model returns Darcy, convert: f_D = 4 f_F.
      * Gravity constant self.G = g (ft/s^2). gc constant self.G_C is used when mixing units for pressure gradient (psf to psi/ft).
      * Survey inclination is measured from vertical; Beggs & Brill angle theta is measured from horizontal.
      * PVT functions are provided by CorrelationBase (e.g., _calculate_fluid_properties, densities, viscosities).
      * Gas-lift orifice model is first-order (Cd*A*sqrt(2*gc*ΔP/ρ)). If valve curves are provided, they take precedence.

    Notes on acceleration:
      * Total gradient: dP/dz = (dP/dz)_elev + (dP/dz)_fric + (dP/dz)_acc
      * (dP/dz)_acc ≈ (1 / (144 * gc)) * d(ρ_m * v_m^2)/dz
      * For robustness, a forward difference is used except at the last step, where it is set to 0.
    """

    # --------------------------- Initialization --------------------------- #
    def __init__(self, data: HydraulicsInput):
        super().__init__(data)
        self.method_name = "Beggs & Brill (1973) + Gas-Lift Hooks"

        # Survey handling (angle from vertical -> theta from horizontal)
        self.survey_data = data.survey_data
        self.theta_default_rad = math.radians(
            90.0 - getattr(self.wellbore, "deviation", 0.0)
        )

        # Gas-lift configuration (optional)
        self.gl_cfg = getattr(data, "gas_lift", None)
        self.gl_enabled = bool(self.gl_cfg and getattr(self.gl_cfg, "enabled", False))
        self.gl_valves = []
        if self.gl_enabled and getattr(self.gl_cfg, "valves", None):
            # sort valves by measured depth (MD)
            self.gl_valves = sorted(self.gl_cfg.valves, key=lambda v: v.md)

        # Internal accumulators / profiles
        n = self.depth_steps
        self.v_sl_profile = np.zeros(n)
        self.v_sg_profile = np.zeros(n)
        self.mixture_velocities = np.zeros(n)
        self.mixture_densities = np.zeros(n)
        self.holdups = np.zeros(n)
        self.flow_patterns: List[FlowPatternEnum] = [FlowPatternEnum.BUBBLE] * n

        self.dpdz_elev = np.zeros(n)
        self.dpdz_fric = np.zeros(n)
        self.dpdz_acc = np.zeros(n)
        self.dpdz_total = np.zeros(n)

        # Gas-lift accounting (surface conditions, standard cubic feet/day, etc.)
        self.qg_injected_cum = 0.0

    # --------------------------- Public entrypoint --------------------------- #
    def calculate_pressure_profile(self):
        """
        Integrates pressure along the wellbore using Beggs & Brill correlation.
        Gas-lift: at each step, if a valve is present and the annulus-to-tubing ΔP is sufficient,
        injects gas according to either (i) provided valve curve or (ii) simple orifice equation.
        """
        p = self.p_wh  # initial pressure at wellhead (or start node) [psia]
        T = self.T_wh  # temperature [°F], could be a profile in a more advanced model

        for i, (pipe_segment, survey_segment) in enumerate(zip(self.wellbore.segments, self._iter_survey())):
            dz = max(pipe_segment.length, 1e-6)        # ft
            D_in = pipe_segment.diameter               # inches
            D = D_in / 12.0                             # ft
            A = self.PI * (D / 2.0) ** 2                # ft^2 (cross-sectional area)
            roughness_rel = self.wellbore.roughness / max(D_in, 1e-9)

            # Convert survey inclination (from vertical) -> theta from horizontal for B&B
            if survey_segment:
                inclination_rad = math.radians(survey_segment.inclination)
                theta_rad = (self.PI / 2.0) - inclination_rad
            else:
                theta_rad = self.theta_default_rad

            # --- Fluid/PVT properties at current conditions ---
            props = self._calculate_fluid_properties(p, T)

            # Convert stock-tank rates to in-situ superficial velocities
            Qo, Qw, Qg_res = self._convert_production_rates(props)  # STB/d, STB/d, scf/d
            # Optionally add gas-lift at this depth
            Qg_inj = 0.0
            if self.gl_enabled:
                Qg_inj = self._gaslift_injection_at_depth(
                    depth=pipe_segment.md, p_tubing=p, T=T
                )
                self.qg_injected_cum += Qg_inj

            Qg_total = Qg_res + Qg_inj
            v_sl, v_sg, v_m = self._calculate_superficial_velocities(Qo, Qw, Qg_total, A)
            self.v_sl_profile[i] = v_sl
            self.v_sg_profile[i] = v_sg
            self.mixture_velocities[i] = v_m

            # No-slip input liquid fraction C_L
            C_L = v_sl / v_m if v_m > 0 else 0.0

            # Phase densities and liquid properties
            rho_o, rho_w, rho_g = self._calculate_fluid_densities(props)      # lbm/ft^3
            rho_liq, mu_liq = self._calculate_liquid_properties(rho_o, rho_w, props)
            # Approximate surface tension (sigma) for N_LV (can be replaced with a better model)
            sigma = self._calculate_surface_tension(p, T, rho_o, rho_w)        # dynes/cm or consistent units

            # ----------------- Beggs & Brill calculations ----------------- #
            # 1) Dimensionless numbers
            N_Fr = (v_m ** 2) / (self.G * D)                     # Froude number
            N_LV = (v_sl * rho_liq / sigma)**0.5 if sigma > 0 else 1e6  # Liquid-viscous number (approx form)

            # 2) Regime boundaries (faithful ordering)
            L1, L2, L3, L4 = self._regime_boundaries(C_L)

            # 3) Flow pattern map
            flow_regime = self._classify_regime(C_L, N_Fr, L1, L2, L3, L4)
            self.flow_patterns[i] = self._map_flow_pattern_enum(flow_regime)

            # 4) Horizontal holdup H_L0
            H_L0 = self._horizontal_holdup(flow_regime, C_L, N_Fr, L2, L3)
            H_L0 = max(H_L0, C_L)

            # 5) Inclination correction B(theta) (keeps sign; clamps at end)
            B_theta = self._inclination_correction(flow_regime, C_L, N_LV, N_Fr, theta_rad)

            # 6) In-situ liquid holdup H_L
            H_L = H_L0 * B_theta
            H_L = max(0.01, min(0.99, H_L))
            self.holdups[i] = H_L

            # 7) Mixture properties (no-slip vs in-situ)
            rho_ns = C_L * rho_liq + (1.0 - C_L) * rho_g                 # lbm/ft^3 (no-slip)
            rho_s  = H_L * rho_liq + (1.0 - H_L) * rho_g                 # lbm/ft^3 (in-situ)
            self.mixture_densities[i] = rho_s

            # 8) Single-phase friction factor (Fanning) at mixture Re
            #    NOTE: _single_phase_fanning_f() must return Fanning. If you only have Darcy, convert.
            v_ns = v_m  # mixture velocity
            mu_m = self._mixture_viscosity(mu_liq, props.mu_g, H_L)  # simple blend or a better model
            Re_m = max(1.0, rho_ns * v_ns * D / max(mu_m, 1e-6))
            f_ns = self._single_phase_fanning_f(Re_m, roughness_rel)  # Fanning friction factor

            # 9) Two-phase friction factor via multiplier S(y)
            f_tp = self._two_phase_fanning_f(f_ns, C_L, H_L)

            # 10) Gradients: elevation, friction, acceleration
            # Elevation term (psi/ft): ρ_s * g / (144 * gc) * sin(theta)
            self.dpdz_elev[i] = rho_s * self.G * math.sin(theta_rad) / (144.0 * self.G_C)

            # Friction term (psi/ft): 2 * f_F * ρ_ns * v_m^2 / (D * 144 * gc)
            self.dpdz_fric[i] = 2.0 * f_tp * rho_ns * (v_m ** 2) / (D * 144.0 * self.G_C)

            # Acceleration term (psi/ft): (1/(144*gc)) * d(ρ_s * v_m^2)/dz  (forward difference)
            if i < self.depth_steps - 1:
                # Predict next step with same rates (explicit Euler predictor)
                p_pred = max(14.7, p - (self.dpdz_elev[i] + self.dpdz_fric[i]) * dz)
                props_next = self._calculate_fluid_properties(p_pred, T)
                rho_o_n, rho_w_n, rho_g_n = self._calculate_fluid_densities(props_next)
                rho_liq_n, _ = self._calculate_liquid_properties(rho_o_n, rho_w_n, props_next)
                # Assume same H_L for prediction (small step approximation)
                rho_s_next = H_L * rho_liq_n + (1.0 - H_L) * rho_g_n
                v_m_next = v_m  # rates constant inside step; can be refined if PVT coupling is strong
                d_rho_vm2_dz = (rho_s_next * (v_m_next ** 2) - rho_s * (v_m ** 2)) / dz
                self.dpdz_acc[i] = d_rho_vm2_dz / (144.0 * self.G_C)
            else:
                self.dpdz_acc[i] = 0.0

            # Total gradient (psi/ft)
            self.dpdz_total[i] = self.dpdz_elev[i] + self.dpdz_fric[i] + self.dpdz_acc[i]

            # Integrate pressure (upstream to downstream)
            p = max(1.0, p - self.dpdz_total[i] * dz)

        # Store results via base class helper
        self._store_results(
            p_profile=None,  # if base expects arrays, provide or compute; else return in get_results()
            holdup=self.holdups,
            flow_patterns=self.flow_patterns,
            v_sl=self.v_sl_profile,
            v_sg=self.v_sg_profile,
            rho_mix=self.mixture_densities,
            dpdz_elev=self.dpdz_elev,
            dpdz_fric=self.dpdz_fric,
            dpdz_acc=self.dpdz_acc,
            dpdz_total=self.dpdz_total,
            qg_injected_cum=self.qg_injected_cum
        )

    # --------------------------- Gas-lift helpers --------------------------- #
    def _gaslift_injection_at_depth(self, depth: float, p_tubing: float, T: float) -> float:
        """
        Computes gas injection rate at a given measured depth (MD).
        If a valve is located near 'depth' and annulus-to-tubing ΔP is sufficient, injects gas.
        Priority order:
            1) If valve_curve is provided -> interpolate q(ΔP).
            2) Else -> orifice equation with Cd and port_diameter.
        Enforces per-valve and total injection upper bounds.
        Returns gas rate at standard conditions (e.g., scf/d). Units must remain consistent downstream.
        """
        if not self.gl_valves:
            return 0.0

        valve = next((v for v in self.gl_valves if abs(v.md - depth) <= getattr(v, "activation_window_md", 5.0)), None)
        if valve is None:
            return 0.0

        # Annulus pressure at depth: use provided profile or simple gas gradient (lightweight fallback)
        p_ann = self._annulus_pressure_at_depth(depth, T)

        # Minimum ΔP requirement
        dp = max(0.0, p_ann - p_tubing - getattr(valve, "delta_p_min", 0.0))
        if dp <= 0.0:
            return 0.0

        # Limit by total supply if provided
        max_total = getattr(self.gl_cfg, "max_total_injection_mscfd", None)
        remaining_total = float("inf") if max_total is None else max(0.0, max_total - self.qg_injected_cum)

        # 1) Valve curve (piecewise), expects list of (dp_psia, q_scfpd)
        if getattr(valve, "valve_curve", None):
            q = self._interp_valve_curve(valve.valve_curve, dp)
        else:
            # 2) Orifice model: q ≈ Cd * A * sqrt( 2*gc*ΔP*144 / ρg )
            Cd = getattr(valve, "Cd", 0.85)
            d_port_in = getattr(valve, "port_diameter", 0.125)  # inches
            A = self.PI * (d_port_in / 12.0 / 2.0) ** 2  # ft^2
            rho_g_ann = self._gas_density_annulus(p_ann, T)     # lbm/ft^3
            # flow_coeff_to_scfpd scales mass/volumetric to SCF/d, keep as 1.0 if dimensions already in scf/d
            flow_coeff_to_scfpd = getattr(valve, "flow_coeff_to_scfpd", 1.0)
            q = Cd * A * math.sqrt(max(0.0, 2.0 * self.G_C * dp * 144.0 / max(rho_g_ann, 1e-9))) * flow_coeff_to_scfpd

        # Per-valve cap
        per_valve = getattr(valve, "max_rate_per_valve_mscfd", None)
        if per_valve is not None:
            q = min(q, per_valve)

        # Total supply cap
        q = min(q, remaining_total)

        # Optional: reduce available supply if gas_source is shared, etc. (not modeled here)
        return max(0.0, q)

    def _annulus_pressure_at_depth(self, depth: float, T: float) -> float:
        """
        Returns annulus pressure at measured depth.
        If a profile is provided, linear-interpolate; otherwise calculates with a simple compressible gas gradient
        based on gas specific gravity and z-model in the gas_lift config. This is a light placeholder
        that should be replaced with a consistent annulus hydraulics if needed.
        """
        # Profile provided by user:
        prof = getattr(self.gl_cfg, "annulus_pressure_profile", None)
        if prof:
            # prof: List[Tuple(md, psia)] expected sorted by md
            if depth <= prof[0][0]:
                return prof[0][1]
            if depth >= prof[-1][0]:
                return prof[-1][1]
            for (md0, p0), (md1, p1) in zip(prof[:-1], prof[1:]):
                if md0 <= depth <= md1:
                    frac = (depth - md0) / max(md1 - md0, 1e-9)
                    return p0 + frac * (p1 - p0)

        # Fallback: constant head at surface + simple gas gradient (very approximate)
        p_surf = getattr(self.gl_cfg, "surface_annulus_pressure", 0.0)
        # Assume light gas column -> small gradient; use sg & Z crude
        sg = getattr(self.gl_cfg, "gas_sg", 0.65)
        z = 0.9
        rho_g = self._rho_gas_from_sg(p_surf, T, sg, z)
        # hydrostatic: dp/dz = rho_g * g / (144 * gc)
        # integrate linearly from surface to depth (MD~TVD simplification)
        return max(14.7, p_surf + rho_g * self.G * (depth - getattr(self.wellbore, "md_top", 0.0)) / (144.0 * self.G_C))

    def _gas_density_annulus(self, p: float, T: float) -> float:
        """Approximate annulus gas density at (p, T). Uses gas_lift gas_sg and z-model if provided."""
        sg = getattr(self.gl_cfg, "gas_sg", 0.65)
        z_model = getattr(self.gl_cfg, "z_model", "Standing")
        z = self._z_factor(p, T, sg, model=z_model)
        return self._rho_gas_from_sg(p, T, sg, z)

    def _rho_gas_from_sg(self, p: float, T: float, sg: float, z: float) -> float:
        """
        Density of gas using pseudo-ideal gas with SG:
           ρg ≈ (28.97 * sg * p) / (z * R * T_R)     [lbm/ft^3]
        where p [psia], T_R [°R], R=10.7316 (psia*ft^3)/(lbmol*°R), 28.97 lbm/lbmol (air).
        """
        R = 10.7316
        T_R = (T + 459.67)
        MW = 28.97 * sg
        return (MW * p) / max(z * R * T_R, 1e-9)

    def _z_factor(self, p: float, T: float, sg: float, model: str = "Standing") -> float:
        """Placeholder for gas compressibility model; keep simple but bounded."""
        # You can replace by DAK/PR/BWRS. Here we keep a bounded heuristic (0.70 .. 1.10).
        return max(0.70, min(1.10, 1.0 - 5e-4 * (p - 1000.0)))

    def _interp_valve_curve(self, curve: List[tuple], dp: float) -> float:
        """Linear interpolation of valve curve points (dp_psia, q_scfpd)."""
        curve = sorted(curve, key=lambda x: x[0])
        if dp <= curve[0][0]:
            return curve[0][1]
        if dp >= curve[-1][0]:
            return curve[-1][1]
        for (dp0, q0), (dp1, q1) in zip(curve[:-1], curve[1:]):
            if dp0 <= dp <= dp1:
                frac = (dp - dp0) / max(dp1 - dp0, 1e-9)
                return q0 + frac * (q1 - q0)
        return 0.0

    # --------------------------- B&B internal pieces --------------------------- #
    def _iter_survey(self):
        """Yield survey segments aligned with wellbore segments (or None)."""
        if self.survey_data:
            for seg in self.survey_data.segments:
                yield seg
        else:
            for _ in self.wellbore.segments:
                yield None

    def _regime_boundaries(self, C_L: float):
        """Returns L1, L2, L3, L4 bounds per Beggs & Brill (1973)."""
        L1 = 316.0 * (C_L ** 0.302)
        L2 = 0.0009252 * (C_L ** -2.468)
        L3 = 0.1 * (C_L ** -1.452)
        L4 = 0.5 * (C_L ** -6.738)
        return L1, L2, L3, L4

    def _classify_regime(self, C_L: float, N_Fr: float, L1: float, L2: float, L3: float, L4: float) -> str:
        """
        Flow regime classification with explicit inequality order to avoid overlaps:
          - Segregated: N_Fr < L1 and C_L >= 0.01
          - Intermittent: (L3 < N_Fr <= L1 and 0.01 <= C_L < 0.4) OR (L3 < N_Fr <= L4 and C_L >= 0.4)
          - Distributed: N_Fr > L4 OR ((C_L < 0.4) and (N_Fr >= L4) and (N_Fr > L3))
          - Transition: L2 <= N_Fr <= L3 (otherwise fallback to Distributed)
        """
        if C_L >= 0.01 and N_Fr < L1:
            return "Segregated"
        if ((0.01 <= C_L < 0.4) and (L3 < N_Fr <= L1)) or ((C_L >= 0.4) and (L3 < N_Fr <= L4)):
            return "Intermittent"
        if (N_Fr > L4) or ((C_L < 0.4) and (N_Fr >= L4) and (N_Fr > L3)):
            return "Distributed"
        if L2 <= N_Fr <= L3:
            return "Transition"
        return "Distributed"

    def _map_flow_pattern_enum(self, regime: str) -> FlowPatternEnum:
        return {
            "Segregated": FlowPatternEnum.STRATIFIED,
            "Intermittent": FlowPatternEnum.SLUG,
            "Distributed": FlowPatternEnum.BUBBLE,
            "Transition": FlowPatternEnum.TRANSITION,
        }.get(regime, FlowPatternEnum.BUBBLE)

    def _horizontal_holdup(self, flow_regime: str, C_L: float, N_Fr: float, L2: float, L3: float) -> float:
        """Beggs & Brill horizontal liquid holdup H_L0 by regime, with Transition blending."""
        reg_params = {
            "Segregated":  (0.980, -0.4846, 0.0868),
            "Intermittent": (0.845, -0.5351, 0.0173),
            "Distributed": (1.065, -0.5822, 0.0609),
        }
        if flow_regime == "Transition":
            a_seg, b_seg, c_seg = reg_params["Segregated"]
            a_int, b_int, c_int = reg_params["Intermittent"]
            H_L0_seg = a_seg * (C_L ** b_seg) / max(N_Fr, 1e-12) ** c_seg
            H_L0_int = a_int * (C_L ** b_int) / max(N_Fr, 1e-12) ** c_int
            A = (L3 - N_Fr) / max(L3 - L2, 1e-12)  # blending factor
            return A * H_L0_seg + (1.0 - A) * H_L0_int
        else:
            a, b, c = reg_params.get(flow_regime, reg_params["Distributed"])
            return a * (C_L ** b) / max(N_Fr, 1e-12) ** c

    def _inclination_correction(self, flow_regime: str, C_L: float, N_LV: float, N_Fr: float, theta_rad: float) -> float:
        """
        Inclination correction factor B(theta) following B&B, preserving sign for uphill/downhill.
        Beta is computed per regime; final B(theta) = 1 + beta * (sin(1.8θ) - (1/3) sin^3(1.8θ)).
        """
        beta = 0.0
        if theta_rad > 1e-6:  # Uphill
            params = {
                "Segregated":  (0.011, -3.768, 3.539, -1.614),
                "Intermittent": (2.96, 0.305, -0.4473, 0.0978),
            }.get(flow_regime)
            if params:
                D, e, f, g_coeff = params
                term = D * (C_L ** e) * (N_LV ** f) * (N_Fr ** g_coeff)
                if term > 0.0:
                    beta = (1.0 - C_L) * math.log(term)
        elif theta_rad < -1e-6:  # Downhill
            D, e, f, g_coeff = 4.7, -0.3692, 0.1244, -0.5056
            term = D * (C_L ** e) * (N_LV ** f) * (N_Fr ** g_coeff)
            if term > 0.0:
                beta = (1.0 - C_L) * math.log(term)

        # Keep sign (do not clamp to positive only); clamp H_L after applying B(theta)
        return 1.0 + beta * (math.sin(1.8 * theta_rad) - (1.0 / 3.0) * (math.sin(1.8 * theta_rad) ** 3))

    def _two_phase_fanning_f(self, f_ns: float, C_L: float, H_L: float) -> float:
        """
        Two-phase friction factor using multiplier S(y), with y = C_L / H_L^2.
        Returns f_tp = f_ns * exp(S). This is the common B&B variant; verify against your reference.
        """
        y = C_L / max(H_L ** 2, 1e-9)
        if y <= 1.0 or y > 1.2:
            ln_y = math.log(max(y, 1e-9))
            S = ln_y / (-0.0523 + 3.182 * ln_y - 0.8725 * (ln_y ** 2) + 0.01853 * (ln_y ** 4))
        else:
            S = math.log(2.2 * y - 1.2)
        return f_ns * math.exp(S)

    # --------------------------- Low-level physical helpers --------------------------- #
    def _mixture_viscosity(self, mu_l: float, mu_g: float, H_L: float) -> float:
        """Simple linear blend; replace by more rigorous model if needed."""
        return max(1e-6, H_L * mu_l + (1.0 - H_L) * mu_g)

    # The following methods are expected to be provided by CorrelationBase in your codebase:
    #   _calculate_fluid_properties(p, T) -> props with fields: rs, mu_o, mu_w, mu_g, etc.
    #   _convert_production_rates(props) -> (Qo, Qw, Qg) at current p,T (STB/d, STB/d, scf/d)
    #   _calculate_fluid_densities(props) -> (rho_o, rho_w, rho_g) [lbm/ft^3]
    #   _calculate_liquid_properties(rho_o, rho_w, props) -> (rho_liq, mu_liq)
    #   _calculate_surface_tension(p, T, rho_o, rho_w) -> sigma
    #   _single_phase_fanning_f(Re, eps_rel) -> f_F




def calculate_beggs_brill(data: HydraulicsInput) -> HydraulicsResult:
    correlation = BeggsBrill(data)
    correlation.calculate_pressure_profile()
    return correlation.get_results()
