from typing import Dict, Any, Optional, Literal
import math
from .gas_pipeline_base import GasPipelineBase


class PanhandleA(GasPipelineBase):
    """
    Implementation of the Panhandle A equation for gas pipeline calculations.

    The Panhandle A equation is specifically designed for:
    - Long-distance gas transmission pipelines
    - Reynolds numbers between 5×10^6 to 1.5×10^7
    - Partial turbulence flow
    - Pipe diameters from 4 to 36+ inches
    """

    def __init__(self,
                 diameter: float,
                 length: float,
                 gas_rate: float,
                 inlet_pressure: float,
                 gas_gravity: float,
                 temperature: float,
                 z_factor: Optional[float] = None,
                 efficiency: float = 0.92):
        """
        Initialize the Panhandle A correlation with the given parameters.

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
        super().__init__(diameter, length, gas_rate, inlet_pressure, gas_gravity,
                         temperature, z_factor, efficiency)
        self.C = 435.87  # Panhandle A constant
        self.n = 0.853  # flow exponent for Panhandle A

    def _calculate_outlet_pressure(self) -> float:
        """
        Calculate outlet pressure using the Panhandle A equation.

        Returns:
            Outlet pressure squared (p2^2) in psia^2
        """
        # Formula: Q = (C * E * d^2.53 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5 * (G)^(0.147))
        # Rearranged for p2^2:
        # p2^2 = p1^2 - [(Q * T_avg^0.5 * G^0.5 * L^0.5 * G^0.147) / (C * E * d^2.53)]^(1/0.5)

        term = (self.gas_rate * math.sqrt(self.t_avg * self.gas_gravity * self.length_miles) *
                self.gas_gravity ** 0.147) / (self.C * self.efficiency * self.diameter ** 2.53)

        return self.inlet_pressure ** 2 - (term ** 2)

    def _calculate_max_flow_rate(self) -> float:
        """
        Calculate maximum gas flow rate using the Panhandle A equation.

        Returns:
            Maximum flow rate in Mscf/d
        """
        # Minimum allowable outlet pressure (could be adjusted based on requirements)
        p2_min = max(14.7, self.inlet_pressure * 0.1)  # 10% of inlet or atmospheric

        # Calculate maximum flow using Panhandle A equation
        max_flow = (self.C * self.efficiency * self.diameter ** 2.53 *
                    math.sqrt(self.inlet_pressure ** 2 - p2_min ** 2)) / \
                   (math.sqrt(self.t_avg * self.gas_gravity * self.length_miles) *
                    self.gas_gravity ** 0.147)

        return max_flow


class PanhandleB(GasPipelineBase):
    """
    Implementation of the Panhandle B equation for gas pipeline calculations.

    The Panhandle B equation is an update to Panhandle A and is designed for:
    - Modern high-pressure gas transmission pipelines
    - Reynolds numbers > 1.5×10^7 (higher than Panhandle A)
    - Very turbulent flow
    - Pipe diameters from 4 to 48+ inches
    """

    def __init__(self,
                 diameter: float,
                 length: float,
                 gas_rate: float,
                 inlet_pressure: float,
                 gas_gravity: float,
                 temperature: float,
                 z_factor: Optional[float] = None,
                 efficiency: float = 0.95):
        """
        Initialize the Panhandle B correlation with the given parameters.

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
        super().__init__(diameter, length, gas_rate, inlet_pressure, gas_gravity,
                         temperature, z_factor, efficiency)
        self.C = 737.0  # Panhandle B constant
        self.n = 0.961  # flow exponent for Panhandle B

    def _calculate_outlet_pressure(self) -> float:
        """
        Calculate outlet pressure using the Panhandle B equation.

        Returns:
            Outlet pressure squared (p2^2) in psia^2
        """
        # Formula: Q = (C * E * d^2.53 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5 * (G)^(0.039))
        # Rearranged for p2^2:
        # p2^2 = p1^2 - [(Q * T_avg^0.5 * G^0.5 * L^0.5 * G^0.039) / (C * E * d^2.53)]^(1/0.5)

        term = (self.gas_rate * math.sqrt(self.t_avg * self.gas_gravity * self.length_miles) *
                self.gas_gravity ** 0.039) / (self.C * self.efficiency * self.diameter ** 2.53)

        return self.inlet_pressure ** 2 - (term ** 2)

    def _calculate_max_flow_rate(self) -> float:
        """
        Calculate maximum gas flow rate using the Panhandle B equation.

        Returns:
            Maximum flow rate in Mscf/d
        """
        # Minimum allowable outlet pressure (could be adjusted based on requirements)
        p2_min = max(14.7, self.inlet_pressure * 0.1)  # 10% of inlet or atmospheric

        # Calculate maximum flow using Panhandle B equation
        max_flow = (self.C * self.efficiency * self.diameter ** 2.53 *
                    math.sqrt(self.inlet_pressure ** 2 - p2_min ** 2)) / \
                   (math.sqrt(self.t_avg * self.gas_gravity * self.length_miles) *
                    self.gas_gravity ** 0.039)

        return max_flow


# Function interfaces to maintain compatibility with existing code
def calculate_panhandle_a(
        diameter: float,
        length: float,
        gas_rate: float,
        inlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 0.92,
) -> Dict[str, Any]:
    """
    Calculate gas flow in a pipeline using the Panhandle A equation.

    Args:
        diameter: Pipe inside diameter in inches
        length: Pipe length in feet
        gas_rate: Gas flow rate in Mscf/d
        inlet_pressure: Inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)

    Returns:
        Dictionary containing calculated results
    """
    panhandle_a = PanhandleA(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature,
        z_factor=z_factor,
        efficiency=efficiency
    )
    return panhandle_a.calculate()


def calculate_panhandle_b(
        diameter: float,
        length: float,
        gas_rate: float,
        inlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 0.95,
) -> Dict[str, Any]:
    """
    Calculate gas flow in a pipeline using the Panhandle B equation.

    Args:
        diameter: Pipe inside diameter in inches
        length: Pipe length in feet
        gas_rate: Gas flow rate in Mscf/d
        inlet_pressure: Inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)

    Returns:
        Dictionary containing calculated results
    """
    panhandle_b = PanhandleB(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature,
        z_factor=z_factor,
        efficiency=efficiency
    )
    return panhandle_b.calculate()


def calculate_max_flow_rate_panhandle(
        equation: Literal["a", "b"],
        diameter: float,
        length: float,
        inlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 0.95,
) -> float:
    """
    Calculate maximum gas flow rate using the Panhandle A or B equation.

    Args:
        equation: Which equation to use - "a" or "b"
        diameter: Pipe inside diameter in inches
        length: Pipe length in feet
        inlet_pressure: Inlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)

    Returns:
        Maximum flow rate in Mscf/d
    """
    if equation.lower() == "a":
        panhandle = PanhandleA(
            diameter=diameter,
            length=length,
            gas_rate=0.0,  # Not used for max flow calculation
            inlet_pressure=inlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )
    else:  # Panhandle B
        panhandle = PanhandleB(
            diameter=diameter,
            length=length,
            gas_rate=0.0,  # Not used for max flow calculation
            inlet_pressure=inlet_pressure,
            gas_gravity=gas_gravity,
            temperature=temperature,
            z_factor=z_factor,
            efficiency=efficiency
        )

    return panhandle._calculate_max_flow_rate()


def calculate_diameter_panhandle(
        equation: Literal["a", "b"],
        gas_rate: float,
        length: float,
        inlet_pressure: float,
        outlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 0.95,
) -> float:
    """
    Calculate required pipe diameter using the Panhandle A or B equation.

    Args:
        equation: Which equation to use - "a" or "b"
        gas_rate: Gas flow rate in Mscf/d
        length: Pipe length in feet
        inlet_pressure: Inlet pressure in psia
        outlet_pressure: Outlet pressure in psia
        gas_gravity: Gas specific gravity (air=1)
        temperature: Average gas temperature in °F
        z_factor: Gas compressibility factor (optional)
        efficiency: Pipeline efficiency factor (0.5-1.0)

    Returns:
        Required pipe diameter in inches
    """
    # Convert units as needed
    length_miles = length / 5280  # convert feet to miles
    t_avg = temperature + 460  # convert °F to °R

    # Calculate z-factor if not provided
    if z_factor is None:
        # Simple z-factor correlation
        p_avg = (inlet_pressure + outlet_pressure) / 2
        p_pr = p_avg / (709 - 58 * gas_gravity)
        t_pr = t_avg / (170 + 314 * gas_gravity)
        z_factor = 1.0 - 0.06 * p_pr / t_pr

    # Panhandle constants
    if equation.lower() == "a":
        C = 435.87
        gravity_exponent = 0.147
    else:  # Panhandle B
        C = 737.0
        gravity_exponent = 0.039

    # Calculate diameter using Panhandle equation
    # Rearranged for d
    term = (gas_rate * math.sqrt(t_avg * gas_gravity * length_miles) * gas_gravity ** gravity_exponent) / \
           (C * efficiency * math.sqrt(inlet_pressure ** 2 - outlet_pressure ** 2))

    diameter = term ** (1 / 2.53)

    return diameter