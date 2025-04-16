# backend/pvt/utils.py
import math

def api_to_sg(api):
    """Convert API gravity to specific gravity (relative to water)."""
    return 141.5 / (api + 131.5)

def to_rankine(temp_f):
    """Convert temperature from Fahrenheit to Rankine."""
    return temp_f + 459.67

def sutton_tpc(gg):
    """Sutton (1985) correlation for pseudo-critical temperature [°R]."""
    return 169.2 + 349.5 * gg - 74.0 * gg**2

def sutton_ppc(gg):
    """Sutton (1985) correlation for pseudo-critical pressure [psia]."""
    return 756.8 - 131.0 * gg - 3.6 * gg**2

def gamma_oil(api):
    """Alias for oil specific gravity."""
    return api_to_sg(api)

def gamma_g(gas_gravity):
    """Pass-through for gas gravity (air = 1)."""
    return gas_gravity

def correct_gas_gravity(gravity_at_p, p, t, api):
    """
    Corrects gas gravity to equivalent at 100 psig separator conditions.
    Using Vazquez-Beggs Equation 1
    
    Args:
        gravity_at_p: Gas gravity at the current separator pressure
        p: Separator pressure in psia
        t: Separator temperature in °F
        api: Oil gravity in °API
        
    Returns:
        Gas gravity corrected to 100 psig separator conditions
    """
    return gravity_at_p * (1.0 + 5.912e-5 * api * t * math.log10(p/114.7))

def rs_limit(rs):
    """Safely cap solution GOR to prevent negative or unreasonable values."""
    return max(0, rs)

def safe_log10(x):
    """Safe base-10 logarithm avoiding log(0) or log of negative numbers."""
    return math.log10(max(x, 1e-10))

def safe_pow(base, exp):
    """Safe power function to handle negative bases and small values."""
    if base < 0 and not exp.is_integer():
        raise ValueError("Cannot raise negative base to fractional exponent.")
    return base ** exp if base != 0 else 0.0