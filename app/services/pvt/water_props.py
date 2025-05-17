# app/services/pvt/water_props.py
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def calculate_water_fvf(temperature: float) -> float:
    """
    Calculate water formation volume factor using McCain correlation.
    
    Args:
        temperature: Temperature in °F
        
    Returns:
        Water formation volume factor (Bw) in bbl/STB
    """
    try:
        # McCain correlation
        bw = 1.0 + 1.2e-4 * (temperature - 60) + 1.0e-6 * (temperature - 60)**2
        
        # Validate result is physical
        if bw <= 0 or bw > 2.0:
            logger.warning(f"Calculated water FVF outside normal range: {bw}")
            bw = max(1.0, min(bw, 2.0))
            
        return bw
        
    except Exception as e:
        logger.error(f"Error in water FVF calculation: {str(e)}")
        return 1.0  # Default to 1.0 in case of calculation error

def calculate_water_viscosity(temperature: float, salinity: Optional[float] = 0.0) -> float:
    """
    Calculate water viscosity using Van Wingen correlation.
    
    Args:
        temperature: Temperature in °F
        salinity: Water salinity in weight percent (optional)
        
    Returns:
        Water viscosity in centipoise (cp)
    """
    try:
        # Base viscosity using Van Wingen correlation
        visc_base = 0.02414 * 10**(248.37/(temperature + 133.15))
        
        # Apply salinity correction if provided
        if salinity > 0:
            # Collins correlation for salinity effect
            s_corr = 1.0 + 0.00087 * salinity + 0.00000456 * salinity**2
            visc = visc_base * s_corr
        else:
            visc = visc_base
            
        # Validate result is physical
        if visc <= 0 or visc > 10.0:
            logger.warning(f"Calculated water viscosity outside normal range: {visc}")
            visc = max(0.2, min(visc, 10.0))
            
        return visc
        
    except Exception as e:
        logger.error(f"Error in water viscosity calculation: {str(e)}")
        return 1.0  # Default to 1.0 cp in case of calculation error

def calculate_water_density(temperature: float, water_gravity: float = 1.0) -> float:
    """
    Calculate water density at reservoir conditions.
    
    Args:
        temperature: Temperature in °F
        water_gravity: Water specific gravity relative to fresh water
        
    Returns:
        Water density in lb/ft³
    """
    try:
        # Base density of fresh water at standard conditions
        std_density = 62.4  # lb/ft³
        
        # Adjust for water gravity
        density = std_density * water_gravity
        
        # Temperature correction (approximate)
        temp_corr = 1.0 - 0.0001 * (temperature - 60)
        density *= temp_corr
        
        return density
        
    except Exception as e:
        logger.error(f"Error in water density calculation: {str(e)}")
        return 62.4 * water_gravity  # Default to standard calculation in case of error