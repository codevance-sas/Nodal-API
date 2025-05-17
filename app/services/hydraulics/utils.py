from typing import Dict, Any
from .pvt_adapter import get_pvt_properties


def calculate_fluid_properties(
    pressure: float,
    temperature: float,
    fluid_props: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate PVT properties at given pressure and temperature
    using the PVT module.
    
    Args:
        pressure: Pressure at which to calculate properties (psia)
        temperature: Temperature at which to calculate properties (°F)
        fluid_props: Dictionary containing fluid properties including:
            - oil_gravity: Oil API gravity
            - gas_gravity: Gas specific gravity (air=1)
            - bubble_point: Bubble point pressure (psia)
            - water_gravity: Water specific gravity (optional, default 1.05)
            - gor: Gas-oil ratio (scf/STB) (optional)
            - temperature: Reservoir temperature (°F) (will be overridden by parameter)
            - correlations: Dictionary of correlation methods (optional)
    
    Returns:
        Dictionary of PVT properties:
            - oil_fvf: Oil formation volume factor (Bo) [RB/STB]
            - oil_viscosity: Oil viscosity (μo) [cp]
            - water_fvf: Water formation volume factor (Bw) [RB/STB]
            - water_viscosity: Water viscosity (μw) [cp]
            - gas_fvf: Gas formation volume factor (Bg) [RB/SCF]
            - gas_viscosity: Gas viscosity (μg) [cp]
            - z_factor: Gas compressibility factor (Z) [dimensionless]
            - solution_gor: Solution gas-oil ratio (Rs) [SCF/STB]
    """
    return get_pvt_properties(pressure, temperature, fluid_props)