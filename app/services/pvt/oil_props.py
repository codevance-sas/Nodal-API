# backend/pvt/oil_props.py

import math
import logging
from app.utils.conversions import api_to_sg, correct_gas_gravity

logger = logging.getLogger(__name__)

# Cache to avoid recalculation and prevent recursion
_pb_cache = {}
_rs_cache = {}
_bo_cache = {}

# Validity ranges for each correlation based on the reference documentation
CORRELATION_RANGES = {
    "standing": {"api": (16.5, 63.8), "gg": (0.5, 1.5), "rs": (20, 1425), "temp": (100, 258)},
    "vazquez_beggs": {"api": (15.3, 59.5), "gg": (0.511, 1.351), "rs": (0, 2000), "temp": (70, 295)},
    "glaso": {"api": (22.3, 48.1), "gg": (0.65, 1.276), "rs": (90, 2637), "temp": (80, 280)},
    "marhoun": {"api": (14.3, 44.6), "gg": (0.752, 1.367), "rs": (24, 1901), "temp": (75, 240)},
    "petrosky": {"api": (16.3, 45), "gg": (0.5781, 0.8519), "rs": (217, 1406), "temp": (114, 288)},
    "beggs_robinson": {"api": (16, 58), "temp": (70, 295)},
    "bergman_sutton": {"api": (10, 50), "temp": (80, 220)}
}

def is_valid_for_correlation(data, method, property_type="general"):
    """Check if input data is within valid range for the correlation."""
    if method not in CORRELATION_RANGES:
        return True, ""
    range_data = CORRELATION_RANGES[method]
    messages = []
    if "api" in range_data and hasattr(data, "api"):
        min_api, max_api = range_data["api"]
        if method == "standing":
            min_api *= 0.9
            max_api *= 1.1
        if data.api < min_api or data.api > max_api:
            messages.append(f"API gravity {data.api} outside ({min_api:.1f}-{max_api:.1f})")
    if "gg" in range_data and hasattr(data, "gas_gravity"):
        min_gg, max_gg = range_data["gg"]
        if data.gas_gravity < min_gg or data.gas_gravity > max_gg:
            messages.append(f"Gas gravity {data.gas_gravity} outside ({min_gg}-{max_gg})")
    if "temp" in range_data and hasattr(data, "temperature"):
        min_temp, max_temp = range_data["temp"]
        if data.temperature < min_temp or data.temperature > max_temp:
            messages.append(f"Temp {data.temperature}°F outside ({min_temp}-{max_temp}°F)")
    if "rs" in range_data and property_type in ["rs", "bo"] and hasattr(data, "gor"):
        min_rs, max_rs = range_data["rs"]
        rs_value = data.gor if property_type == "rs" else getattr(data, "rs", data.gor)
        if rs_value < min_rs or rs_value > max_rs:
            messages.append(f"Rs {rs_value} SCF/STB outside ({min_rs}-{max_rs})")
    return len(messages) == 0, "; ".join(messages)

def recommend_correlation(data, prop):
    """Recommend the best correlation based on fluid properties."""
    api, gor, temp = data.api, data.gor, data.temperature
    if api < 20:
        return "vazquez_beggs" if prop in ["pb", "rs", "bo"] else "bergman_sutton"
    if api > 40:
        return "petrosky" if gor >= 1000 and prop in ["pb", "rs", "bo"] else "standing"
    if prop in ["pb", "rs", "bo"]:
        return "petrosky" if gor > 1000 and temp > 200 else "glaso" if gor > 1000 else "standing"
    return {
        "mu": "beggs_robinson",
        "co": "vazquez_beggs",
        "rho": "standing",
        "z": "sutton",
        "ift": "asheim"
    }.get(prop, "standing")

def calculate_pb(data, method=None, validate=True, from_rs_calc=False, _recursion_depth=0):
    """
    Calculate bubble point pressure using various correlations.
    
    Args:
        data: PVTInput object with required properties
        method: Correlation method to use
        validate: Whether to validate input ranges
        from_rs_calc: Flag to indicate if this was called from calculate_rs to avoid circular calls
        _recursion_depth: Counter to limit recursion depth
        
    Returns:
        Bubble point pressure in psia
    """
    # Protect against infinite recursion
    if _recursion_depth > 2:
        logger.warning("Excessive recursion depth in calculate_pb, using fallback value")
        return min(max(14.7, 5 * data.gor), 5000)  # Fallback estimate
    
    method = method or recommend_correlation(data, "pb")
    rs, T, api, gg = float(data.gor), float(data.temperature), float(data.api), float(data.gas_gravity)
    
    # Create a cache key from inputs
    cache_key = f"{api}_{gg}_{rs}_{T}_{method}"
    
    # Check cache first
    if cache_key in _pb_cache:
        return _pb_cache[cache_key]
    
    if validate:
        is_valid, msg = is_valid_for_correlation(data, method, "pb")
        if not is_valid:
            logger.warning(f"PB correlation warning: {msg}")
    
    # If the gas gravity is from a separator at a different pressure than 100 psig,
    # it should be corrected - if stock_pressure is available
    if hasattr(data, "stock_pressure") and data.stock_pressure != 114.7:
        stock_temp = getattr(data, "stock_temp", 60.0)  # Default to 60°F if not provided
        gg = correct_gas_gravity(gg, data.stock_pressure, stock_temp, api)
    
    try:
        if method == "vazquez_beggs":
            # Use the correct coefficients from Vazquez-Beggs paper
            if api <= 30:
                C1, C2, C3 = 0.0362, 1.0937, 25.7240
            else:
                C1, C2, C3 = 0.0178, 1.1870, 23.9310
            
            # Rearranged formula from Rs equation based on Vazquez-Beggs
            # Pb = (Rs / (C1 * G * exp(C3 * γo / (T+460)))) ^ (1/C2)
            pb = (rs / (C1 * gg * math.exp(C3 * api / (T + 459.67)))) ** (1.0 / C2)
            
            # Add a more realistic cap
            result = min(pb, 10000.0)
            
        elif method == "glaso":
            # Using the Glaso correlation from the documentation
            # Pb = 10^log(Pb) where log(Pb) = 1.7669 + 1.7447 * log(x) - 0.30218 * log(x)^2
            # where x = (Rs/γg)^0.816 * T^0.172 / γAPI^0.989
            
            log_x = math.log10((rs / gg) ** 0.816 * T ** 0.172 / (api ** 0.989))
            log_pb = 1.7669 + 1.7447 * log_x - 0.30218 * log_x**2
            result = 10 ** log_pb
            
        elif method == "marhoun":
            # Al-Marhoun correlation for Middle East oils
            # Pb = 112.727 * (Rs/γg)^0.5774 * 10^(0.000524*T - 0.0006226*API)
            gamma_o = api_to_sg(api)
            result = 112.727 * (rs / gg) ** 0.5774 * 10 ** (0.000524 * T - 0.0006226 * api)
            
        elif method == "petrosky":
            # Petrosky and Farshad correlation for Gulf of Mexico oils
            # First calculate the x term
            x = 4.561e-5 * T**1.3911 - 7.916e-4 * api**1.541
            # Then calculate Pb
            result = 112.727 * ((rs**0.5774) / (gg**0.8439) * 10**x - 12.34)
            
        else:  # Standing correlation
            # Standing's correlation
            # Pb = 18.2 * ((Rs/G)^0.83 * 10^(0.00091*T - 0.0125*API) - 1.4)
            result = 18.2 * (rs / gg) ** 0.83 * 10 ** (0.00091 * T - 0.0125 * api) - 1.4
        
        # Cap result at 10,000 psia for stability
        result = min(max(14.7, result), 10000.0)
        
        # Store result in cache
        _pb_cache[cache_key] = result
        return result
            
    except Exception as e:
        logger.error(f"PB calc error with {method}: {str(e)}")
        result = min(max(14.7, 5 * rs), 5000)
        _pb_cache[cache_key] = result
        return result

def calculate_rs(data, pressure=None, pb=None, method=None, validate=True, _recursion_depth=0):
    """
    Calculate solution gas-oil ratio (Rs) using various correlations.
    
    Args:
        data: PVTInput object with required properties
        pressure: Pressure at which to calculate Rs (psia)
        pb: Bubble point pressure (psia) - optional
        method: Correlation method to use
        validate: Whether to validate input ranges
        _recursion_depth: Counter to limit recursion depth
        
    Returns:
        Solution gas-oil ratio in scf/STB
    """
    # Protect against infinite recursion
    if _recursion_depth > 2:
        logger.warning("Excessive recursion depth in calculate_rs, using fallback value")
        # Simple linear interpolation as fallback
        pb_est = getattr(data, "pb", 2000) or 2000  # Use 2000 as fallback if needed
        return min(data.gor * (pressure or data.pressure) / pb_est, data.gor)
    
    pressure = pressure or getattr(data, "pressure", None)
    if pressure is None:
        logger.warning("No pressure provided for Rs calculation")
        return data.gor  # Default to GOR if no pressure
    
    method = method or recommend_correlation(data, "rs")
    
    # Get bubble point if not provided, but avoid recursive calls
    if pb is None:
        if hasattr(data, "pb") and data.pb is not None and data.pb > 0:
            pb = float(data.pb)
        else:
            # Calculate pb with flag to prevent recursion
            pb = calculate_pb(data, method=method, from_rs_calc=True, _recursion_depth=_recursion_depth+1)
    
    # Create a cache key
    cache_key = f"{data.api}_{data.gas_gravity}_{data.temperature}_{pressure}_{pb}_{method}"
    
    # Check cache first
    if cache_key in _rs_cache:
        return _rs_cache[cache_key]
    
    # Above bubble point, Rs = constant = GOR
    if pressure >= pb:
        _rs_cache[cache_key] = data.gor
        return data.gor
    
    # Below bubble point, calculate Rs based on correlation
    T, api, gg = data.temperature, data.api, data.gas_gravity
    gamma_o = api_to_sg(api)  # Convert API to specific gravity
    
    # If the gas gravity is from a separator at a different pressure than 100 psig,
    # it should be corrected - if stock_pressure is available
    if hasattr(data, "stock_pressure") and data.stock_pressure != 114.7:
        stock_temp = getattr(data, "stock_temp", 60.0)  # Default to 60°F if not provided
        gg = correct_gas_gravity(gg, data.stock_pressure, stock_temp, api)
    
    try:
        if method == "vazquez_beggs":
            # Vazquez-Beggs correlation (Equation 2)
            if api <= 30:
                C1, C2, C3 = 0.0362, 1.0937, 25.7240
            else:
                C1, C2, C3 = 0.0178, 1.1870, 23.9310
            
            # Rs = C1 * G * P^C2 * exp[C3 * γo/(T+460)] from Vazquez-Beggs
            rs = C1 * gg * (pressure ** C2) * math.exp(C3 * api / (T + 459.67))
            
        elif method == "glaso":
            # Glaso correlation - solved for Rs from the Pb equation
            # First calculate x needed for the equation
            if pressure <= 0:
                rs = 0
            else:
                # Calculate log(x)
                a = -0.30218
                b = 1.7447
                c = 1.7669 - math.log10(pressure)
                
                # Quadratic formula to find log(x)
                if b**2 - 4*a*c < 0:
                    # Fallback when equation has no real solutions
                    rs = data.gor * (pressure / pb)
                else:
                    log_x = (-b + math.sqrt(b**2 - 4*a*c)) / (2*a)
                    x = 10**log_x
                    
                    # Now solve for Rs: Rs = x * γAPI^0.989 * γg / T^0.172
                    rs = x * api**0.989 * gg / (T**0.172)
                    
                    # Ensure Rs doesn't exceed GOR at bubble point
                    rs = min(rs, data.gor)
            
        elif method == "marhoun":
            # Al-Marhoun correlation for Middle East oils
            # Rs = γg * (pressure / (112.727 * 10^(0.000524*T - 0.0006226*API)))^(1/0.5774)
            exp_term = 0.000524 * T - 0.0006226 * api
            rs = gg * (pressure / (112.727 * 10 ** exp_term)) ** (1 / 0.5774)
            
        elif method == "petrosky":
            # Petrosky and Farshad correlation for Gulf of Mexico oils
            # First calculate the x term
            x = 7.916e-4 * api**1.541 - 4.561e-5 * T**1.3911
            # Then calculate Rs
            if pressure <= 0:
                rs = 0
            else:
                rs = ((pressure / 112.727 + 12.34) * gg**0.8439 * 10**x) ** 1.73184
            
        else:  # Standing
            # Standing correlation
            # Rs = G * (p / (18.2 * 10^(0.00091*T - 0.0125*API)) + 1.4)^(1/0.83)
            if pressure <= 0:
                rs = 0
            else:
                rs = gg * ((pressure / 18.2 / 10 ** (0.00091 * T - 0.0125 * api)) + 1.4) ** (1 / 0.83)
        
        # Rs cannot exceed GOR
        result = min(max(0, rs), data.gor)
        
        # Store result in cache
        _rs_cache[cache_key] = result
        return result
            
    except Exception as e:
        logger.error(f"RS error @ {pressure} psia using {method}: {str(e)}")
        # Linear interpolation as fallback
        result = max(0, data.gor * (pressure / pb))
        _rs_cache[cache_key] = result
        return result

def calculate_bo(data, rs=None, pb=None, pressure=None, method=None, validate=True, _recursion_depth=0):
    """
    Calculate oil formation volume factor (Bo) using various correlations.
    
    For P ≤ Pb: Uses specific correlation equation for saturated oil
    For P > Pb: Uses Bo = Bob·exp[Co(Pb-P)] for undersaturated oil
    
    Args:
        data: PVTInput object with required properties
        rs: Solution gas-oil ratio (scf/STB) - optional
        pb: Bubble point pressure (psia) - optional
        pressure: Pressure (psia) - optional, if provided with pb, handles undersaturated conditions
        method: Correlation method to use
        validate: Whether to validate input ranges
        _recursion_depth: Counter to limit recursion depth
        
    Returns:
        Oil formation volume factor in bbl/STB
    """
    # Protect against infinite recursion
    if _recursion_depth > 2:
        logger.warning("Excessive recursion depth in calculate_bo, using fallback value")
        return 1.0 + 0.0005 * (rs or data.gor) + 0.0004 * (data.temperature - 60)  # Simple fallback
    
    method = method or recommend_correlation(data, "bo")
    
    # Get bubble point if not provided
    if pb is None:
        if hasattr(data, "pb") and data.pb is not None and data.pb > 0:
            pb = float(data.pb)
        else:
            pb = calculate_pb(data, method=method, _recursion_depth=_recursion_depth+1)
    
    pressure = pressure or getattr(data, "pressure", None)
    
    # Create a cache key
    cache_key = f"{data.api}_{data.gas_gravity}_{data.temperature}_{pressure or 0}_{pb}_{rs or 0}_{method}"
    
    # Check cache first
    if cache_key in _bo_cache:
        return _bo_cache[cache_key]
    
    # Handle undersaturated case if both pressure and pb are provided
    if pressure is not None and pressure > pb:
        # First calculate Bo at bubble point
        rs_at_pb = data.gor  # At bubble point, Rs = GOR
        bo_at_pb = calculate_bo(data, rs=rs_at_pb, pb=pb, pressure=None, method=method, _recursion_depth=_recursion_depth+1)
        
        # Then apply compressibility correction using Bo = Bob·exp[Co(Pb-P)]
        co_method = getattr(data, "correlations", {}).get("co", recommend_correlation(data, "co"))
        co = calculate_co(data, rs=rs_at_pb, pb=pb, method=co_method)
        
        result = bo_at_pb * math.exp(co * (pb - pressure))
        _bo_cache[cache_key] = result
        return result
    
    # Saturated oil calculation (P ≤ Pb)
    if rs is None:
        if pressure is not None:
            rs = calculate_rs(data, pressure=pressure, pb=pb, method=method, _recursion_depth=_recursion_depth+1)
        elif hasattr(data, "pressure") and data.pressure is not None:
            rs = calculate_rs(data, pressure=data.pressure, pb=pb, method=method, _recursion_depth=_recursion_depth+1)
        else:
            rs = data.gor  # Default to GOR if no pressure data
    
    T, gg, api = data.temperature, data.gas_gravity, data.api
    gamma_o = api_to_sg(api)  # Convert API to specific gravity
    
    # If the gas gravity is from a separator at a different pressure than 100 psig,
    # it should be corrected - if stock_pressure is available
    if hasattr(data, "stock_pressure") and data.stock_pressure != 114.7:
        stock_temp = getattr(data, "stock_temp", 60.0)  # Default to 60°F if not provided
        gg = correct_gas_gravity(gg, data.stock_pressure, stock_temp, api)
    
    try:
        if method == "vazquez_beggs":
            # Use Equation 3 from Vazquez-Beggs paper
            if api > 30:
                A1, A2, A3 = 4.670e-4, 1.100e-5, 1.337e-9
            else:
                A1, A2, A3 = 4.677e-4, 1.751e-5, -1.811e-8
            
            # Bo = 1 + A1·Rs + A2(T-60)(γo/G) + A3·Rs(T-60)(γo/G)
            result = 1.0 + A1 * rs + A2 * (T - 60) * (gamma_o / gg) + A3 * rs * (T - 60) * (gamma_o / gg)
        
        elif method == "glaso":
            # Glaso correlation for North Sea oils
            # log(Bo-1) = -6.58511 + 2.91329·log(y) - 0.27683·log(y)^2
            # where y = Rs·(γg/γo)^0.526 + 0.968·T
            y = rs * (gg / gamma_o) ** 0.526 + 0.968 * T
            
            # Avoid log of negative values
            if y <= 0:
                result = 1.05  # Fallback
            else:
                log_bo_minus_1 = -6.58511 + 2.91329 * math.log10(y) - 0.27683 * math.log10(y)**2
                result = 1.0 + 10 ** log_bo_minus_1
            
        elif method == "marhoun":
            # Al-Marhoun correlation for Middle East oils
            # Bo = 0.497069 + 0.000862·Rs + 0.000123·Rs·(γg/γo)^0.5 + 0.000194·T
            result = 0.497069 + 0.000862 * rs + 0.000123 * rs * (gg / gamma_o) ** 0.5 + 0.000194 * T
            
        elif method == "petrosky":
            # Petrosky and Farshad correlation for Gulf of Mexico oils
            # Much more complex equation - using the simplified form
            result = 1.0113 + 0.000072 * (rs * (gg / gamma_o) ** 0.5 + 1.25 * T) ** 1.2
            
        else:  # Standing correlation
            # Bo = 0.972 + 1.47×10^-4 * (Rs * (G/γo)^0.5 + 1.25*T)^1.175
            result = 0.972 + 1.47e-4 * (rs * (gg / gamma_o) ** 0.5 + 1.25 * T) ** 1.175
        
        # Store result in cache
        _bo_cache[cache_key] = result
        return result
            
    except Exception as e:
        logger.error(f"BO error: {str(e)}")
        # Simple fallback based on typical behavior
        result = 1.0 + 0.0005 * rs + 0.0004 * (T - 60)
        _bo_cache[cache_key] = result
        return result

def calculate_co(data, rs=None, pb=None, method="vazquez_beggs", validate=True, _recursion_depth=0):
    """
    Calculate oil compressibility using various correlations.
    
    Args:
        data: PVTInput object with required properties
        rs: Solution gas-oil ratio (scf/STB) - optional
        pb: Bubble point pressure (psia) - optional
        method: Correlation method to use
        validate: Whether to validate input ranges
        _recursion_depth: Counter to limit recursion depth
        
    Returns:
        Oil compressibility in 1/psi
    """
    # Protect against infinite recursion
    if _recursion_depth > 2:
        logger.warning("Excessive recursion depth in calculate_co, using fallback value")
        return 5e-6  # Simple fallback
    
    pressure = getattr(data, "pressure", 14.7)
    
    # Get bubble point if not provided
    if pb is None:
        if hasattr(data, "pb") and data.pb is not None and data.pb > 0:
            pb = float(data.pb)
        else:
            pb = calculate_pb(data, method=method, _recursion_depth=_recursion_depth+1)
    
    # Get Rs if not provided
    if rs is None and pressure is not None:
        rs = calculate_rs(data, pressure=min(pressure, pb), pb=pb, method=method, _recursion_depth=_recursion_depth+1)
    
    T, gg = float(data.temperature), float(data.gas_gravity)
    api = float(data.api)
    gamma_o = api_to_sg(api)  # Convert API to oil specific gravity
    
    # If the gas gravity is from a separator at a different pressure than 100 psig,
    # it should be corrected - if stock_pressure is available
    if hasattr(data, "stock_pressure") and data.stock_pressure != 114.7:
        stock_temp = getattr(data, "stock_temp", 60.0)  # Default to 60°F if not provided
        gg = correct_gas_gravity(gg, data.stock_pressure, stock_temp, api)
    
    try:
        if method == "vazquez_beggs":
            if pressure <= pb:
                # Below bubble point - use typical value per industry practice
                return 5e-6  
            
            # Using Equation 5 from Vazquez-Beggs paper
            # Co = (-1433 + 5Rs + 17.2T - 1180G + 12.61γo) / (10^5 × p)
            numerator = -1433.0 + 5.0 * rs + 17.2 * T - 1180.0 * gg + 12.61 * api
            return max(1e-7, numerator / (1e5 * pressure))
            
        elif method == "standing":
            # Standing's simple correlation for undersaturated oil
            return max(1e-7, 5e-5 * (1000 / pressure) ** 0.5)
        
        elif method == "petrosky":
            # Petrosky and Farshad correlation
            if pressure <= pb:
                return 5e-6  # Below bubble point
            
            # More complex equation, using Vazquez-Beggs as fallback
            numerator = -1433.0 + 5.0 * rs + 17.2 * T - 1180.0 * gg + 12.61 * api
            return max(1e-7, numerator / (1e5 * pressure))
            
        return 5e-6  # Default fallback
        
    except Exception as e:
        logger.error(f"CO error: {str(e)}")
        return 5e-6

def calculate_mu_o(data, rs=None, pb=None, method=None, validate=True, _recursion_depth=0):
    """
    Calculate oil viscosity using various correlations.
    
    Args:
        data: PVTInput object with required properties
        rs: Solution gas-oil ratio (scf/STB) - optional
        pb: Bubble point pressure (psia) - optional
        method: Correlation method to use
        validate: Whether to validate input ranges
        _recursion_depth: Counter to limit recursion depth
        
    Returns:
        Oil viscosity in centipoise
    """
    # Protect against infinite recursion
    if _recursion_depth > 2:
        logger.warning("Excessive recursion depth in calculate_mu_o, using fallback value")
        return max(0.2, 1000 * math.exp(-0.3 * data.api) / (1 + 0.001 * (rs or data.gor)))  # Simple fallback
    
    method = method or recommend_correlation(data, "mu")
    
    # Get bubble point if not provided
    if pb is None:
        if hasattr(data, "pb") and data.pb is not None and data.pb > 0:
            pb = float(data.pb)
        else:
            pb = calculate_pb(data, method=recommend_correlation(data, "pb"), _recursion_depth=_recursion_depth+1)
    
    # Get Rs if not provided
    if rs is None:
        if hasattr(data, "pressure") and data.pressure is not None:
            rs = calculate_rs(data, pressure=data.pressure, pb=pb, method=recommend_correlation(data, "rs"), _recursion_depth=_recursion_depth+1)
        else:
            rs = data.gor  # Default to GOR if no pressure provided
    
    api, T = data.api, data.temperature
    pressure = getattr(data, "pressure", None)
    
    try:
        if method == "beggs_robinson":
            # Calculate dead oil viscosity using Beggs and Robinson correlation
            z = 3.0324 - 0.02023 * api
            mu_dead = 10 ** (10 ** z * T ** (-1.163)) - 1.0
            
            # Apply correction for solution gas
            a = 10.715 * (rs + 100) ** (-0.515)
            b = 5.44 * (rs + 150) ** (-0.338)
            
            mu_saturated = a * mu_dead ** b
            
            # If pressure is above bubble point, apply pressure correction
            if pressure is not None and pressure > pb:
                # Live Oil - Undersaturated (Vazquez-Beggs)
                m = 2.6 * pressure ** 1.187 * math.exp(-11.513 - 8.98e-5 * pressure)
                return mu_saturated * (pressure / pb) ** m
            
            return mu_saturated
            
        elif method == "bergman_sutton":
            # Bergman-Sutton modification of the Beggs-Robinson correlation
            z = 3.0324 - 0.02023 * api
            mu_dead = 10 ** (10 ** z * T ** (-1.163)) - 1.0
            mu_dead *= (12.5 / 10) ** 0.7  # Bergman-Sutton adjustment
            
            # Apply correction for solution gas
            a = 10.715 * (rs + 100) ** (-0.515)
            b = 5.44 * (rs + 150) ** (-0.338)
            
            mu_saturated = a * mu_dead ** b
            
            # If pressure is above bubble point, apply pressure correction
            if pressure is not None and pressure > pb:
                # Live Oil - Undersaturated (Vazquez-Beggs)
                m = 2.6 * pressure ** 1.187 * math.exp(-11.513 - 8.98e-5 * pressure)
                return mu_saturated * (pressure / pb) ** m
            
            return mu_saturated
            
        else:
            # Default to Beggs-Robinson
            z = 3.0324 - 0.02023 * api
            mu_dead = 10 ** (10 ** z * T ** (-1.163)) - 1.0
            
            # Apply correction for solution gas
            a = 10.715 * (rs + 100) ** (-0.515)
            b = 5.44 * (rs + 150) ** (-0.338)
            
            return a * mu_dead ** b
        
    except Exception as e:
        logger.error(f"Mu_o error: {str(e)}")
        return max(0.2, 1000 * math.exp(-0.3 * api) / (1 + 0.001 * rs))

def calculate_rho_o(data, rs=None, bo=None, method="standing", validate=True, _recursion_depth=0):
    """
    Calculate oil density using various correlations.
    
    Args:
        data: PVTInput object with required properties
        rs: Solution gas-oil ratio (scf/STB) - optional
        bo: Oil formation volume factor - optional
        method: Correlation method to use
        validate: Whether to validate input ranges
        _recursion_depth: Counter to limit recursion depth
        
    Returns:
        Oil density in lb/ft³
    """
    # Protect against infinite recursion
    if _recursion_depth > 2:
        logger.warning("Excessive recursion depth in calculate_rho_o, using fallback value")
        rho_sto = api_to_sg(data.api) * 62.4
        return rho_sto / (1 + 0.001 * (rs or data.gor))  # Simple fallback
    
    pressure = getattr(data, "pressure", None)
    
    # Get bubble point if not provided
    if hasattr(data, "pb") and data.pb is not None and data.pb > 0:
        pb = float(data.pb)
    else:
        pb = calculate_pb(data, method=recommend_correlation(data, "pb"), _recursion_depth=_recursion_depth+1)
    
    # Get Rs if not provided
    if rs is None and pressure is not None:
        rs = calculate_rs(data, pressure=pressure, pb=pb, method=recommend_correlation(data, "rs"), _recursion_depth=_recursion_depth+1)
    elif rs is None:
        rs = data.gor  # Default to GOR if no pressure
    
    # Get Bo if not provided
    if bo is None:
        bo = calculate_bo(data, rs=rs, pb=pb, method=recommend_correlation(data, "bo"), _recursion_depth=_recursion_depth+1)
    
    rho_sto = api_to_sg(data.api) * 62.4  # Stock tank oil density in lb/ft³
    
    try:
        if method == "standing":
            # Standing correlation - most widely used
            # ρo = (ρsto + 0.0136 * γg * Rs) / Bo
            return (rho_sto + 0.0136 * data.gas_gravity * rs) / bo
        
        elif method == "vazquez_beggs":
            # Vazquez-Beggs density correlation
            # ρo = (ρsto + 0.01357 * γg * Rs) / Bo
            return (rho_sto + 0.01357 * data.gas_gravity * rs) / bo
        
        else:
            # Simple correlation (base method)
            # ρo = ρsto / Bo
            return rho_sto / bo
            
    except Exception as e:
        logger.error(f"Rho_o error: {str(e)}")
        return rho_sto / (1 + 0.001 * rs)