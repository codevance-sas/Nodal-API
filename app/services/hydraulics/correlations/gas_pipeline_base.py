from abc import ABC, abstractmethod
import math
from typing import Dict, Any, Optional, Tuple

class GasPipelineBase(ABC):
    """
    Base class for gas pipeline correlation methods.
    
    This class provides common functionality for gas pipeline calculations,
    including z-factor calculation, Reynolds number calculation, and friction factor calculation.
    
    Subclasses must implement the `_calculate_outlet_pressure` method to perform the actual
    pressure drop calculation using the specific correlation method.
    """
    PI = math.pi
    G = 32.2  # Acceleration due to gravity, ft/s²
    G_C = 32.17  # Conversion factor, ft-lbm/lbf-s²
    
    def __init__(self, 
                 diameter: float,
                 length: float,
                 gas_rate: float,
                 inlet_pressure: float,
                 gas_gravity: float,
                 temperature: float,
                 z_factor: Optional[float] = None,
                 efficiency: float = 1.0):
        """
        Initialize the gas pipeline correlation with the given parameters.
        
        Args:
            diameter: Pipe inside diameter in inches
            length: Pipe length in feet
            gas_rate: Gas flow rate in Mscf/d
            inlet_pressure: Inlet pressure in psia
            gas_gravity: Gas specific gravity (air=1)
            temperature: Average gas temperature in °F
            z_factor: Gas compressibility factor (optional)
            efficiency: Pipeline efficiency factor (0.5-1.0)
        """
        self.diameter = diameter  # inches
        self.length = length  # feet
        self.length_miles = length / 5280  # convert feet to miles
        self.gas_rate = gas_rate  # Mscf/d
        self.inlet_pressure = inlet_pressure  # psia
        self.gas_gravity = gas_gravity  # air=1
        self.temperature = temperature  # °F
        self.t_avg = temperature + 460  # convert °F to °R
        self.efficiency = efficiency  # 0.5-1.0
        
        # Calculate z-factor if not provided
        if z_factor is None:
            self.z_factor = self._calculate_z_factor()
        else:
            self.z_factor = z_factor
    
    def _calculate_z_factor(self) -> float:
        """
        Calculate gas compressibility factor using a simplified correlation.
        
        Returns:
            Gas compressibility factor (z-factor)
        """
        # Simple z-factor correlation (more accurate methods exist in the PVT module)
        p_avg = self.inlet_pressure * 0.75  # rough estimate of average pressure
        p_pr = p_avg / (709 - 58 * self.gas_gravity)  # reduced pressure
        t_pr = self.t_avg / (170 + 314 * self.gas_gravity)  # reduced temperature
        return 1.0 - 0.06 * p_pr / t_pr  # simplified correlation
    
    def _calculate_gas_viscosity(self) -> Tuple[float, float]:
        """
        Calculate gas viscosity using a simplified correlation.
        
        Returns:
            Tuple of (gas_viscosity_cp, gas_viscosity_lbft) where:
            - gas_viscosity_cp: Gas viscosity in centipoise
            - gas_viscosity_lbft: Gas viscosity in lb-sec/ft²
        """
        # Simplified viscosity correlation for natural gas (in centipoise)
        gas_visc_cp = 0.01 + 0.002 * self.gas_gravity
        # Convert to lb-sec/ft² for Reynolds calculation
        gas_visc_lbft = gas_visc_cp * 6.72e-4
        return gas_visc_cp, gas_visc_lbft
    
    def _calculate_gas_density(self, pressure: float) -> float:
        """
        Calculate gas density at the given pressure.
        
        Args:
            pressure: Gas pressure in psia
            
        Returns:
            Gas density in lb/ft³
        """
        # Density at given conditions (lb/ft³)
        return 0.0764 * self.gas_gravity * pressure / (self.z_factor * self.t_avg) * 520/14.7
    
    def _calculate_flow_area(self) -> float:
        """
        Calculate flow area of the pipe.
        
        Returns:
            Flow area in square feet
        """
        return self.PI * (self.diameter/24)**2
    
    def _calculate_actual_flow_rate(self, avg_pressure: float) -> float:
        """
        Calculate actual flow rate at average pressure.
        
        Args:
            avg_pressure: Average pressure in psia
            
        Returns:
            Actual flow rate in ft³/s
        """
        # Convert Mscf/d to actual ft³/s at average conditions
        return self.gas_rate * 1000 * (14.7/avg_pressure) * (self.t_avg/520) * self.z_factor / 86400
    
    def _calculate_velocity(self, actual_flow_rate: float, area: float) -> float:
        """
        Calculate gas velocity.
        
        Args:
            actual_flow_rate: Actual flow rate in ft³/s
            area: Flow area in square feet
            
        Returns:
            Gas velocity in ft/s
        """
        return actual_flow_rate / area
    
    def _calculate_reynolds_number(self, velocity: float, density: float, viscosity_lbft: float) -> float:
        """
        Calculate Reynolds number.
        
        Args:
            velocity: Gas velocity in ft/s
            density: Gas density in lb/ft³
            viscosity_lbft: Gas viscosity in lb-sec/ft²
            
        Returns:
            Reynolds number
        """
        # Reynolds number = (density * velocity * diameter) / viscosity
        return density * velocity * (self.diameter/12) / viscosity_lbft
    
    def _calculate_friction_factor(self, reynolds: float, rel_roughness: float = 0.0006) -> float:
        """
        Calculate Darcy-Weisbach friction factor.
        
        Args:
            reynolds: Reynolds number
            rel_roughness: Relative roughness (default: 0.0006)
            
        Returns:
            Friction factor
        """
        if reynolds < 2000:
            # Laminar flow
            return 64.0 / reynolds
        else:
            # Turbulent flow - Colebrook-White equation (approximation)
            rel_roughness_d = rel_roughness / self.diameter
            return (-1.8 * math.log10((rel_roughness_d/3.7)**1.11 + 6.9/reynolds))**-2
    
    def _determine_flow_regime(self, reynolds: float) -> str:
        """
        Determine flow regime based on Reynolds number.
        
        Args:
            reynolds: Reynolds number
            
        Returns:
            Flow regime ("Laminar", "Transitional", or "Turbulent")
        """
        if reynolds < 2000:
            return "Laminar"
        elif reynolds < 4000:
            return "Transitional"
        else:
            return "Turbulent"
    
    @abstractmethod
    def _calculate_outlet_pressure(self) -> float:
        """
        Calculate outlet pressure using the specific correlation method.
        
        Returns:
            Outlet pressure in psia
        """
        raise NotImplementedError
    
    def calculate(self) -> Dict[str, Any]:
        """
        Calculate gas flow in a pipeline using the specific correlation method.
        
        Returns:
            Dictionary containing calculated results
        """
        # Calculate outlet pressure
        p2_squared = self._calculate_outlet_pressure()
        
        # Ensure we don't have negative pressure (could happen with very high flow rates)
        if p2_squared <= 0:
            outlet_pressure = 14.7  # set to atmospheric if calculation gives invalid result
            pressure_drop = self.inlet_pressure - outlet_pressure
            is_valid = False
            max_flow = self._calculate_max_flow_rate()
        else:
            outlet_pressure = math.sqrt(p2_squared)
            pressure_drop = self.inlet_pressure - outlet_pressure
            is_valid = True
            max_flow = None
        
        # Calculate average gas velocity (ft/s)
        avg_pressure = (self.inlet_pressure + outlet_pressure) / 2
        # Flow area in square feet
        area = self._calculate_flow_area()
        # Convert Mscf/d to actual ft³/s at average conditions
        actual_flow_rate = self._calculate_actual_flow_rate(avg_pressure)
        velocity = self._calculate_velocity(actual_flow_rate, area)
        
        # Calculate Reynolds number
        # Simplified viscosity correlation for natural gas
        _, gas_visc_lbft = self._calculate_gas_viscosity()
        # Density at average conditions (lb/ft³)
        gas_density = self._calculate_gas_density(avg_pressure)
        # Reynolds number
        reynolds = self._calculate_reynolds_number(velocity, gas_density, gas_visc_lbft)
        
        # Calculate friction factor
        friction_factor = self._calculate_friction_factor(reynolds)
        
        # Determine flow regime
        flow_regime = self._determine_flow_regime(reynolds)
        
        # Return calculation results
        return {
            "inlet_pressure": self.inlet_pressure,
            "outlet_pressure": outlet_pressure,
            "pressure_drop": pressure_drop,
            "flow_velocity": velocity,
            "reynolds_number": reynolds,
            "friction_factor": friction_factor,
            "flow_regime": flow_regime,
            "z_factor": self.z_factor,
            "is_valid": is_valid,
            "max_flow": max_flow
        }
    
    @abstractmethod
    def _calculate_max_flow_rate(self) -> float:
        """
        Calculate maximum gas flow rate using the specific correlation method.
        
        Returns:
            Maximum flow rate in Mscf/d
        """
        raise NotImplementedError