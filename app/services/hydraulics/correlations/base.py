from app.schemas.hydraulics import HydraulicsInput, HydraulicsResult, PressurePoint, FlowPatternEnum, FlowPatternResult
from ..utils import calculate_fluid_properties
import math
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List

class CorrelationBase(ABC):
    """
    Base class for all hydraulic correlation methods.
    
    This class provides common functionality and data structures used by all correlation methods,
    including pipe segment and survey segment calculations, fluid property calculations,
    and result formatting.
    
    Subclasses must implement the `calculate_pressure_profile` method to perform the actual
    pressure profile calculation using the specific correlation method.
    """
    PI = math.pi
    G = 32.2  # Acceleration due to gravity, ft/s²
    G_C = 32.17  # Conversion factor, ft-lbm/lbf-s²
    
    def __init__(self, data: HydraulicsInput):
        """
        Initialize the correlation with the given hydraulics input data.
        
        Args:
            data: The hydraulics input data containing fluid properties, wellbore geometry,
                 surface pressure, and optional survey data.
        """
        self.data = data    
        self.fluid = data.fluid_properties
        self.wellbore = data.wellbore_geometry
        # Sort pipe segments by start_depth to ensure correct processing order
        self.wellbore.pipe_segments.sort(key=lambda s: s.start_depth)
        self.surface_pressure = data.surface_pressure
        self.survey_data = data.survey_data
        if self.survey_data:
            self.survey_data.sort(key=lambda s: s.md)

        self.depth_steps = self.wellbore.depth_steps
        self.depth_points = np.linspace(0, self.wellbore.pipe_segments[-1].end_depth, self.depth_steps)

        # Initialize arrays for results
        self.pressures = np.zeros(self.depth_steps)
        self.temperatures = np.zeros(self.depth_steps)
        self.holdups = np.zeros(self.depth_steps)
        self.flow_patterns = [None] * self.depth_steps
        self.mixture_densities = np.zeros(self.depth_steps)
        self.mixture_velocities = np.zeros(self.depth_steps)
        self.friction_factors = np.zeros(self.depth_steps)
        self.reynolds_numbers = np.zeros(self.depth_steps)
        self.dpdz_elevation = np.zeros(self.depth_steps)
        self.dpdz_friction = np.zeros(self.depth_steps)
        self.dpdz_acceleration = np.zeros(self.depth_steps)
        self.dpdz_total = np.zeros(self.depth_steps)
        self.v_sl_profile = np.zeros(self.depth_steps)
        self.v_sg_profile = np.zeros(self.depth_steps)

        # Set initial conditions
        self.pressures[0] = self.surface_pressure
        self.temperatures = self.fluid.surface_temperature + self.fluid.temperature_gradient * self.depth_points

    def _calculate_pipe_segment(self, depth: float):
        """
        Find the pipe segment that contains the given depth.
        
        Args:
            depth: The measured depth to find the pipe segment for.
            
        Returns:
            The pipe segment that contains the given depth, or the last pipe segment
            if the depth is beyond all segments.
        """
        for segment in self.wellbore.pipe_segments:
            if segment.start_depth <= depth <= segment.end_depth:
                return segment
        return self.wellbore.pipe_segments[-1]
        
    def _calculate_survey_segment(self, depth: float):
        """
        Find the survey segment that contains the given depth.
        
        Args:
            depth: The measured depth to find the survey segment for.
            
        Returns:
            The survey segment that contains the given depth, or the last survey segment
            if the depth is beyond all segments, or None if no survey data is available.
        """
        if not self.survey_data:
            return None
        for i in range(len(self.survey_data) - 1):
            if self.survey_data[i].md <= depth < self.survey_data[i+1].md:
                return self.survey_data[i]
        return self.survey_data[-1]

    def _calculate_fluid_properties(self, p: float, T: float) -> Dict[str, Any]:
        """
        Calculate fluid properties at the given pressure and temperature.
        
        Args:
            p: Pressure in psia
            T: Temperature in °F
            
        Returns:
            Dictionary of fluid properties including oil_fvf, water_fvf, gas_fvf,
            oil_viscosity, water_viscosity, gas_viscosity, etc.
        """
        return calculate_fluid_properties(
            p, T, {
                "oil_gravity": self.fluid.oil_gravity,
                "gas_gravity": self.fluid.gas_gravity,
                "bubble_point": self.fluid.bubble_point,
                "water_gravity": self.fluid.water_gravity
            }
        )

    def _convert_production_rates(self, props: Dict[str, Any]) -> Tuple[float, float, float]:
        """
        Convert production rates from standard conditions to reservoir conditions.
        
        Args:
            props: Dictionary of fluid properties
            
        Returns:
            Tuple of (oil_flow_ft3day, water_flow_ft3day, gas_flow_ft3day)
        """
        Qo = self.fluid.oil_rate * 5.615 * props["oil_fvf"]
        Qw = self.fluid.water_rate * 5.615 * props["water_fvf"]
        Qg = self.fluid.gas_rate * 1000 * props["gas_fvf"]
        return Qo, Qw, Qg

    def _calculate_superficial_velocities(self, Qo: float, Qw: float, Qg: float, A: float) -> Tuple[float, float, float]:
        """
        Calculate superficial velocities for liquid and gas phases.
        
        Args:
            Qo: Oil flow rate in ft³/day
            Qw: Water flow rate in ft³/day
            Qg: Gas flow rate in ft³/day
            A: Cross-sectional area in ft²
            
        Returns:
            Tuple of (v_sl, v_sg, v_m) where:
            - v_sl: Superficial liquid velocity in ft/s
            - v_sg: Superficial gas velocity in ft/s
            - v_m: Mixture velocity in ft/s
        """
        v_sl = (Qo + Qw) / (86400 * A)
        v_sg = Qg / (86400 * A)
        v_m = v_sl + v_sg
        return v_sl, v_sg, v_m

    def _calculate_fluid_densities(self, props: Dict[str, Any]) -> Tuple[float, float, float]:
        """
        Calculate densities for oil, water, and gas phases.
        
        Args:
            props: Dictionary of fluid properties
            
        Returns:
            Tuple of (rho_o, rho_w, rho_g) where:
            - rho_o: Oil density in lb/ft³
            - rho_w: Water density in lb/ft³
            - rho_g: Gas density in lb/ft³
        """
        rho_o = 62.4 / props["oil_fvf"]
        rho_w = 62.4 * self.fluid.water_gravity / props["water_fvf"]
        rho_g = 0.0764 * self.fluid.gas_gravity / props["gas_fvf"]
        return rho_o, rho_w, rho_g

    def _calculate_liquid_properties(self, rho_o: float, rho_w: float, props: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calculate weighted average properties for the liquid phase.
        
        Args:
            rho_o: Oil density in lb/ft³
            rho_w: Water density in lb/ft³
            props: Dictionary of fluid properties
            
        Returns:
            Tuple of (rho_liq, mu_liq) where:
            - rho_liq: Liquid density in lb/ft³
            - mu_liq: Liquid viscosity in cp
        """
        q_tot_liq = self.fluid.oil_rate + self.fluid.water_rate
        rho_liq = (self.fluid.oil_rate * rho_o + self.fluid.water_rate * rho_w) / q_tot_liq if q_tot_liq > 0 else 0
        mu_liq = (self.fluid.oil_rate * props["oil_viscosity"] + self.fluid.water_rate * props["water_viscosity"]) / q_tot_liq if q_tot_liq > 0 else 0
        return rho_liq, mu_liq
        
    def _calculate_surface_tension(self, p: float, T: float) -> Tuple[float, float]:
        """
        Calculate surface tension between liquid and gas phases.
        
        Args:
            p: Pressure in psia
            T: Temperature in °F
            
        Returns:
            Tuple of (sigma, sigma_lbf_ft) where:
            - sigma: Surface tension in dynes/cm
            - sigma_lbf_ft: Surface tension in lbf/ft
        """
        # Calculate surface tension for oil-gas and water-gas interfaces
        sigma_oil_gas = max(1.0, 30.0 - 0.1 * (T - 60.0) - 0.005 * (p - 14.7))
        sigma_water_gas = max(5.0, 70.0 - 0.15 * (T - 60.0) - 0.01 * (p - 14.7))
        
        # Calculate weighted average surface tension
        total_liquid_rate = self.fluid.oil_rate + self.fluid.water_rate
        if total_liquid_rate > 0:
            oil_fraction = self.fluid.oil_rate / total_liquid_rate
            water_fraction = self.fluid.water_rate / total_liquid_rate
            sigma = oil_fraction * sigma_oil_gas + water_fraction * sigma_water_gas
        else:
            sigma = sigma_oil_gas  # Default to oil-gas if no liquid
            
        # Convert from dynes/cm to lbf/ft
        sigma_lbf_ft = sigma * 6.85e-5
        
        return sigma, sigma_lbf_ft
        
    def _calculate_elevation_gradient(self, rho: float, inclination_rad: float) -> float:
        """
        Calculate elevation pressure gradient.
        
        Args:
            rho: Fluid density in lb/ft³
            inclination_rad: Inclination angle in radians (from vertical)
            
        Returns:
            Elevation pressure gradient in psi/ft
        """
        return rho * self.G * math.cos(inclination_rad) / (144.0 * self.G_C)
        
    def _calculate_friction_gradient(self, f: float, rho: float, v: float, D: float) -> float:
        """
        Calculate friction pressure gradient.
        
        Args:
            f: Friction factor
            rho: Fluid density in lb/ft³
            v: Fluid velocity in ft/s
            D: Pipe diameter in ft
            
        Returns:
            Friction pressure gradient in psi/ft
        """
        return f * rho * v**2 / (2.0 * self.G_C * D * 144.0)
        
    def _set_flow_pattern(self, i: int, regime: str) -> None:
        """
        Set flow pattern based on regime name.
        
        Args:
            i: Index in the flow_patterns array
            regime: Flow regime name (e.g., "Bubble", "Slug", "Annular", etc.)
        """
        regime_lower = regime.lower()
        if "bubble" in regime_lower:
            self.flow_patterns[i] = FlowPatternEnum.BUBBLE
        elif "slug" in regime_lower:
            self.flow_patterns[i] = FlowPatternEnum.SLUG
        elif "churn" in regime_lower or "transition" in regime_lower:
            self.flow_patterns[i] = FlowPatternEnum.TRANSITION
        elif "annular" in regime_lower or "mist" in regime_lower:
            self.flow_patterns[i] = FlowPatternEnum.ANNULAR
        elif "stratified" in regime_lower or "wavy" in regime_lower:
            self.flow_patterns[i] = FlowPatternEnum.STRATIFIED
        else:
            # Default to bubble flow if regime is unknown
            self.flow_patterns[i] = FlowPatternEnum.BUBBLE

    def _calculate_friction_factor(self, Re: float, roughness_rel: float) -> float:
        """
        Calculate Darcy-Weisbach friction factor based on Reynolds number and relative roughness.
        
        Args:
            Re: Reynolds number
            roughness_rel: Relative roughness (roughness/diameter)
            
        Returns:
            Friction factor (Darcy-Weisbach)
        """
        if Re > 2100:
            # Turbulent flow - Colebrook-White equation (approximation)
            return (-1.8 * math.log10((roughness_rel / 3.7)**1.11 + 6.9 / Re))**-2
        else:
            # Laminar flow
            return 64.0 / Re

    @abstractmethod
    def calculate_pressure_profile(self):
        raise NotImplementedError

    def get_results(self) -> HydraulicsResult:
        pressure_profile = [
            PressurePoint(
                depth=self.depth_points[i],
                pressure=self.pressures[i],
                temperature=self.temperatures[i],
                flow_pattern=self.flow_patterns[i],
                liquid_holdup=self.holdups[i],
                mixture_density=self.mixture_densities[i],
                mixture_velocity=self.mixture_velocities[i],
                reynolds_number=self.reynolds_numbers[i],
                friction_factor=self.friction_factors[i],
                dpdz_elevation=self.dpdz_elevation[i],
                dpdz_friction=self.dpdz_friction[i],
                dpdz_acceleration=self.dpdz_acceleration[i],
                dpdz_total=self.dpdz_total[i]
            ) for i in range(self.depth_steps)
        ]

        dz = self.wellbore.pipe_segments[-1].end_depth / (self.depth_steps - 1) if self.depth_steps > 1 else 0
        total_elevation = np.trapz(self.dpdz_elevation, self.depth_points) if self.depth_steps > 1 else 0
        total_friction = np.trapz(self.dpdz_friction, self.depth_points) if self.depth_steps > 1 else 0
        total_acceleration = np.trapz(self.dpdz_acceleration, self.depth_points) if self.depth_steps > 1 else 0
        total_drop = total_elevation + total_friction + total_acceleration

        return HydraulicsResult(
            method=self.method_name,
            pressure_profile=pressure_profile,
            surface_pressure=self.surface_pressure,
            bottomhole_pressure=self.pressures[-1],
            overall_pressure_drop=self.pressures[-1] - self.surface_pressure,
            elevation_drop_percentage=(total_elevation / total_drop) * 100 if total_drop > 0 else 0,
            friction_drop_percentage=(total_friction / total_drop) * 100 if total_drop > 0 else 0,
            acceleration_drop_percentage=(total_acceleration / total_drop) * 100 if total_drop > 0 else 0,
            flow_patterns=[
                FlowPatternResult(
                    depth=self.depth_points[i],
                    flow_pattern=self.flow_patterns[i] or FlowPatternEnum.BUBBLE,
                    liquid_holdup=self.holdups[i],
                    mixture_velocity=self.mixture_velocities[i],
                    superficial_liquid_velocity=self.v_sl_profile[i],
                    superficial_gas_velocity=self.v_sg_profile[i],
                ) for i in range(0, self.depth_steps, max(1, self.depth_steps // 20))
            ]
        )
    
    