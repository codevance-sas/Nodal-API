from typing import Dict, Any, Optional
import math
from .gas_pipeline_base import GasPipelineBase


class Weymouth(GasPipelineBase):
    """
    Implementation of the Weymouth equation for gas pipeline calculations.

    The Weymouth equation is specifically designed for gas pipelines and is valid for:
    - High-pressure gas flow (completely turbulent)
    - Reynolds numbers > 4000
    - Pipe diameters from 2 to 60 inches
    - Primarily used for transmission pipelines
    """

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
        Initialize the Weymouth correlation with the given parameters.

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
        self.C = 433.5  # Weymouth constant

    def _calculate_outlet_pressure(self) -> float:
        """
        Calculate outlet pressure using the Weymouth equation.

        Returns:
            Outlet pressure squared (p2^2) in psia^2
        """
        # Formula: Q = (C * E * d^2.667 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5)
        # Rearranged for p2^2:
        # p2^2 = p1^2 - [(Q * T_avg^0.5 * G^0.5 * L^0.5) / (C * E * d^2.667)]^2

        term = (self.gas_rate * math.sqrt(self.t_avg * self.gas_gravity * self.length_miles)) / \
               (self.C * self.efficiency * self.diameter ** 2.667)

        return self.inlet_pressure ** 2 - term ** 2

    def _calculate_max_flow_rate(self) -> float:
        """
        Calculate maximum gas flow rate using the Weymouth equation.

        Returns:
            Maximum flow rate in Mscf/d
        """
        # Minimum allowable outlet pressure (could be adjusted based on requirements)
        p2_min = max(14.7, self.inlet_pressure * 0.1)  # 10% of inlet or atmospheric

        # Calculate maximum flow using Weymouth equation
        max_flow = (self.C * self.efficiency * self.diameter ** 2.667 *
                    math.sqrt(self.inlet_pressure ** 2 - p2_min ** 2)) / \
                   (math.sqrt(self.t_avg * self.gas_gravity * self.length_miles))

        return max_flow


# Function interfaces to maintain compatibility with existing code
def calculate_weymouth(
        diameter: float,
        length: float,
        gas_rate: float,
        inlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 1.0,
) -> Dict[str, Any]:
    """
    Calculate gas flow in a pipeline using the Weymouth equation.

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
    weymouth = Weymouth(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature,
        z_factor=z_factor,
        efficiency=efficiency
    )
    return weymouth.calculate()


def calculate_max_flow_rate(
        diameter: float,
        length: float,
        inlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 1.0,
) -> float:
    """
    Calculate maximum gas flow rate using the Weymouth equation.

    Args:
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
    weymouth = Weymouth(
        diameter=diameter,
        length=length,
        gas_rate=0.0,  # Not used for max flow calculation
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature,
        z_factor=z_factor,
        efficiency=efficiency
    )
    return weymouth._calculate_max_flow_rate()


def calculate_diameter_weymouth(
        gas_rate: float,
        length: float,
        inlet_pressure: float,
        outlet_pressure: float,
        gas_gravity: float,
        temperature: float,
        z_factor: Optional[float] = None,
        efficiency: float = 1.0,
) -> float:
    """
    Calculate required pipe diameter using the Weymouth equation.

    Args:
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

    # Weymouth constant
    C = 433.5

    # Calculate diameter using Weymouth equation
    # Q = (C * E * d^2.667 * (p1^2 - p2^2)^0.5) / (T_avg^0.5 * G^0.5 * L^0.5)
    # Rearranged for d:
    # d = [(Q * T_avg^0.5 * G^0.5 * L^0.5) / (C * E * (p1^2 - p2^2)^0.5)]^(1/2.667)

    term = (gas_rate * math.sqrt(t_avg * gas_gravity * length_miles)) / \
           (C * efficiency * math.sqrt(inlet_pressure ** 2 - outlet_pressure ** 2))

    diameter = term ** (1 / 2.667)

    return diameter