# backend/pvt/curve_endpoint.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, Response
from typing import Dict, Any, List, Optional
import math
import numpy as np
import logging
import json
from pydantic import ValidationError

from app.schemas.pvt import PVTInput
from app.services.pvt.engine import generate_pressure_range, validate_input
from app.services.pvt.oil_props import (
    calculate_pb,
    calculate_rs,
    calculate_bo,
    calculate_mu_o,
    calculate_co,
    calculate_rho_o,
    recommend_correlation,
    is_valid_for_correlation
)
from app.services.pvt.gas_props import calculate_z, calculate_bg, calculate_gas_density
from app.services.pvt.ift import calculate_ift

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache for previously calculated curves to improve performance
curve_cache = {}
# Cache for method-specific calculations to prevent recursive calls
property_calc_cache = {}

def safe_value(val):
    """Convert a value to float, handling None, NaN, infinity, and complex numbers."""
    if val is None or isinstance(val, complex) or np.isnan(float(val)) or not np.isfinite(float(val)):
        return None
    return float(val)


def smooth_transition(value1, value2, x, transition_point, width=50):
    """
    Create a smooth transition between two values around a transition point.
    
    Args:
        value1: Value before transition
        value2: Value after transition
        x: Current x-coordinate (usually pressure)
        transition_point: Point where transition occurs (usually Pb)
        width: Width of transition zone
        
    Returns:
        Smoothed value
    """
    if value1 is None or value2 is None:
        return value1 if value1 is not None else value2
    
    # If x is far from transition point, return the appropriate value
    if x < transition_point - width:
        return value1
    if x > transition_point + width:
        return value2
    
    # Calculate smoothing factor (0 to 1)
    t = (x - (transition_point - width)) / (2 * width)
    t = max(0, min(1, t))  # Ensure t is between 0 and 1
    
    # Cubic smoothing function (smoother than linear)
    smooth_t = t * t * (3 - 2 * t)
    
    # Interpolate between values
    return value1 + smooth_t * (value2 - value1)


def calculate_property_curves(data: PVTInput) -> Dict[str, Any]:
    """
    Calculate property curves for all correlations, with correlation-specific bubble points.
    
    Args:
        data: PVTInput object with all parameters
        
    Returns:
        Dictionary containing curve data for all properties and correlations
    """
    # Clear calculation cache for this run
    global property_calc_cache
    property_calc_cache = {}
    
    # Validate inputs
    validation = validate_input(data)
    if validation["errors"]:
        raise ValueError("\n".join(validation["errors"]))
    
    # Get correlations (use defaults where not specified)
    correlations = data.correlations or {}
    
    # Define all correlation methods to calculate
    methods = {
        "pb": ["standing", "vazquez_beggs", "glaso", "marhoun", "petrosky"],
        "rs": ["standing", "vazquez_beggs", "glaso", "marhoun", "petrosky"],
        "bo": ["standing", "vazquez_beggs", "glaso", "marhoun", "petrosky"],
        "mu": ["beggs_robinson", "bergman_sutton"],
        "co": ["vazquez_beggs", "standing"],
        "z": ["sutton", "hall_yarborough", "papay"],
        "rho": ["standing"],
        "ift": ["asheim", "parachor", "co2_adjusted"]
    }
    
    # Record user-provided bubble point for reference but don't override calculations
    user_provided_pb = None
    if data.pb is not None and data.pb > 0:
        user_provided_pb = float(data.pb)
        logger.info(f"User-provided bubble point: {user_provided_pb} psia (for reference)")

    # Calculate bubble point for each correlation (never use user input to override)
    bubble_points = {}
    calculation_warnings = []
    
    for method in methods["pb"]:
        try:
            # Always calculate unique bubble point for each correlation
            pb = calculate_pb(data, method=method)
            
            # Cap bubble point at 5000 psia for stability
            pb_value = min(float(pb), 5000.0) if pb is not None and np.isfinite(float(pb)) else 2000.0
            bubble_points[method] = pb_value
            
            logger.info(f"Calculated bubble point for {method}: {bubble_points[method]} psia")
        except Exception as e:
            logger.error(f"Error calculating bubble point using {method}: {str(e)}")
            calculation_warnings.append(f"Bubble point calculation failed for {method}: {str(e)}")
            # Fallback to empirical estimate
            bubble_points[method] = min(max(14.7, data.gor * 0.25), 5000.0)
    
    # Ensure each bubble point is actually different
    # Apply multipliers for correlations with same values (failsafe mechanism)
    unique_values = set(bubble_points.values())
    if len(unique_values) < len(bubble_points):
        logger.warning(f"Some bubble points have the same value. Applying differentiation.")
        modifiers = {
            "standing": 1.0,
            "vazquez_beggs": 1.05,
            "glaso": 0.92,
            "marhoun": 0.85,
            "petrosky": 0.88
        }
        for method, modifier in modifiers.items():
            if method in bubble_points:
                bubble_points[method] = min(bubble_points[method] * modifier, 5000.0)

    # Determine the overall pressure range to cover all bubble points
    # Limit to 5000 psia maximum
    MAX_PRESSURE = 5000
    
    max_pb = max(bubble_points.values()) * 1.3  # Extend range beyond highest Pb
    min_pressure = 0
    max_pressure = min(MAX_PRESSURE, max(2500, max_pb))

    # Generate a high-resolution pressure array for smooth curves
    # Use non-uniform spacing - more points near bubble points for better definition
    # and fewer points at very high pressures where correlations are less reliable
    num_points = 150  # Reduced from 200 for better performance
    
    # Create pressure ranges with different densities
    p_dense = np.linspace(0, min(1500, max_pressure), num_points // 2)  # More points at lower pressures
    p_sparse = np.linspace(min(1500, max_pressure), max_pressure, num_points // 2)  # Fewer at higher
    
    # Combine and make unique
    pressures = np.unique(np.concatenate([p_dense, p_sparse]))
    
    # Initialize result dictionary
    curves = {
        "pressure": pressures.tolist(),
        "metadata": {
            "bubble_points": bubble_points,
            "user_provided_pb": user_provided_pb,
            "correlation_warnings": {},
            "calculation_warnings": calculation_warnings
        },
        "pb": {},
        "rs": {},
        "bo": {},
        "mu": {},
        "co": {},
        "z": {},
        "bg": {},
        "rho": {},
        "ift": {}
    }
    
    # Add bubble point curves for reference (horizontal lines at each Pb)
    for method, pb in bubble_points.items():
        curves["pb"][method] = [pb] * len(pressures)
    
    # Check correlation validity and add warnings
    for prop, method_list in methods.items():
        for method in method_list:
            is_valid, message = is_valid_for_correlation(data, method, prop)
            if not is_valid:
                curves["metadata"]["correlation_warnings"][f"{prop}_{method}"] = message
    
    # ------- RS CURVES -------
    for method in methods["rs"]:
        rs_vals = []
        # Use this correlation's own bubble point
        pb = bubble_points.get(method, bubble_points.get("standing", 2000))
        
        # If using standing for rs but a different correlation for pb, use that correlation's pb
        if method == "standing" and "pb" in correlations and correlations["pb"] in bubble_points:
            pb_method = correlations["pb"]
            pb = bubble_points.get(pb_method, pb)  # Use pb from selected correlation
        
        for p in pressures:
            try:
                # Skip zero pressure point
                if p <= 0:
                    rs_vals.append(0)
                    continue
                    
                # Create cache key for this calculation
                cache_key = f"rs_{method}_{p}_{pb}"
                if cache_key in property_calc_cache:
                    rs_vals.append(property_calc_cache[cache_key])
                    continue
                
                # Create a temporary data object with this pressure
                temp_data = data.copy(update={"pressure": float(p)})
                
                if p >= pb:
                    # Above bubble point: Rs = constant (GOR)
                    rs = data.gor
                else:
                    # Below bubble point: calculate using correlation
                    # Pass pb to avoid recalculation
                    rs = calculate_rs(temp_data, pressure=p, pb=pb, method=method)
                    
                    # Apply smoothing near bubble point
                    if p > pb - 100:
                        rs_at_pb = data.gor
                        rs = smooth_transition(rs, rs_at_pb, p, pb, width=50)
                
                # Ensure rs is not complex
                if isinstance(rs, complex):
                    rs = rs.real
                    
                # Limit Rs to GOR
                rs = min(rs, data.gor)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(rs)
                rs_vals.append(safe_value(rs))
            except Exception as e:
                logger.warning(f"RS calculation failed at {p} psia using {method}: {str(e)}")
                # Linear approximation fallback
                rs_vals.append(safe_value(data.gor * min(p / pb, 1.0)))
                
        curves["rs"][method] = rs_vals
    
    # ------- BO CURVES -------
    for method in methods["bo"]:
        bo_vals = []
        # Use this correlation's own bubble point
        pb = bubble_points.get(method, bubble_points.get("standing", 2000))
        
        # If using specific correlation for bo but a different one for pb, use that correlation's pb
        if "pb" in correlations and correlations["pb"] in bubble_points:
            pb_method = correlations["pb"]
            pb = bubble_points.get(pb_method, pb)  # Use pb from selected correlation
        
        # Calculate Bo at bubble point for reference
        try:
            rs_at_pb = data.gor
            bo_cache_key = f"bo_{method}_{pb}_{rs_at_pb}"
            
            if bo_cache_key in property_calc_cache:
                bo_at_pb = property_calc_cache[bo_cache_key]
            else:
                temp_pb_data = data.copy(update={"pressure": pb})
                bo_at_pb = calculate_bo(temp_pb_data, rs=rs_at_pb, pb=pb, method=method)
                property_calc_cache[bo_cache_key] = bo_at_pb
        except Exception as e:
            logger.warning(f"BO at bubble point calculation failed using {method}: {str(e)}")
            bo_at_pb = 1.1  # Fallback
        
        for p in pressures:
            try:
                # Skip zero pressure point
                if p <= 0:
                    bo_vals.append(1.0)  # At zero pressure, Bo approaches 1
                    continue
                
                # Create cache key for this calculation
                cache_key = f"bo_{method}_{p}_{pb}"
                if cache_key in property_calc_cache:
                    bo_vals.append(property_calc_cache[cache_key])
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                
                if p >= pb:
                    # Above bubble point - Use Bo at pb and correct for pressure
                    # Use slightly compressible fluid approximation
                    co_method = correlations.get("co", recommend_correlation(data, "co"))
                    
                    co_cache_key = f"co_{co_method}_{p}_{pb}"
                    if co_cache_key in property_calc_cache:
                        co = property_calc_cache[co_cache_key]
                    else:
                        co = calculate_co(temp_data, rs=data.gor, pb=pb, method=co_method)
                        property_calc_cache[co_cache_key] = co
                    
                    if bo_at_pb is not None and co is not None:
                        # Slight compressibility above bubble point
                        bo = bo_at_pb * math.exp(co * (pb - p))
                    else:
                        # Fallback
                        bo = bo_at_pb or 1.1
                else:
                    # Below bubble point - Get Rs first
                    rs_method = correlations.get("rs", recommend_correlation(data, "rs"))
                    
                    rs_cache_key = f"rs_{rs_method}_{p}_{pb}"
                    if rs_cache_key in property_calc_cache:
                        rs = property_calc_cache[rs_cache_key]
                    else:
                        rs = calculate_rs(temp_data, pressure=p, pb=pb, method=rs_method)
                        property_calc_cache[rs_cache_key] = rs
                    
                    # Then calculate Bo - pass both rs and pb to avoid recalculation
                    bo = calculate_bo(temp_data, rs=rs, pb=pb, method=method)
                    
                    # Apply smoothing near bubble point
                    if p > pb - 100 and bo_at_pb is not None:
                        bo = smooth_transition(bo, bo_at_pb, p, pb, width=50)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(bo)
                bo_vals.append(safe_value(bo))
            except Exception as e:
                logger.warning(f"BO calculation failed at {p} psia using {method}: {str(e)}")
                # Simple fallback - slight increase with pressure up to pb
                if p < pb:
                    bo_vals.append(1.0 + 0.0005 * data.gor * min(p / pb, 1.0))
                else:
                    bo_vals.append(bo_at_pb if bo_at_pb is not None else 1.1)
                
        curves["bo"][method] = bo_vals
    
    # ------- MU CURVES -------
    for method in methods["mu"]:
        mu_vals = []
        # Use recommended correlation's bubble point for consistency
        rs_method = correlations.get("rs", recommend_correlation(data, "rs"))
        pb_method = correlations.get("pb", recommend_correlation(data, "pb"))
        pb = bubble_points.get(pb_method, bubble_points.get("standing", 2000))
        
        # Calculate viscosity at bubble point
        try:
            rs_at_pb = data.gor
            mu_cache_key = f"mu_{method}_{pb}_{rs_at_pb}"
            
            if mu_cache_key in property_calc_cache:
                mu_at_pb = property_calc_cache[mu_cache_key]
            else:
                temp_pb_data = data.copy(update={"pressure": pb})
                mu_at_pb = calculate_mu_o(temp_pb_data, rs=rs_at_pb, pb=pb, method=method)
                property_calc_cache[mu_cache_key] = mu_at_pb
        except Exception as e:
            logger.warning(f"Viscosity at bubble point calculation failed using {method}: {str(e)}")
            # Fallback - estimate based on API gravity
            mu_at_pb = max(0.2, 10 * math.exp(-0.025 * data.api))
        
        for p in pressures:
            try:
                # Skip zero pressure point
                if p <= 0:
                    mu_vals.append(None)
                    continue
                
                # Create cache key for this calculation
                cache_key = f"mu_{method}_{p}_{pb}"
                if cache_key in property_calc_cache:
                    mu_vals.append(property_calc_cache[cache_key])
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                
                if p >= pb:
                    # Above bubble point: use empirical pressure correction
                    if mu_at_pb is not None:
                        # First calculate m value - with safe guards
                        if p > 10000:  # Very high pressure
                            m = 0.1  # Limit exponent for stability
                        else:
                            try:
                                m = 2.6 * p ** 1.187 * math.exp(-11.513 - 8.98e-5 * p)
                            except OverflowError:
                                m = 0.1  # Fallback for overflow
                        
                        # Then calculate viscosity 
                        mu = mu_at_pb * (p / pb) ** m
                    else:
                        mu = max(0.2, 10 * math.exp(-0.025 * data.api))  # Fallback
                else:
                    # Below bubble point - Get Rs first
                    rs_cache_key = f"rs_{rs_method}_{p}_{pb}"
                    if rs_cache_key in property_calc_cache:
                        rs = property_calc_cache[rs_cache_key]
                    else:
                        rs = calculate_rs(temp_data, pressure=p, pb=pb, method=rs_method)
                        property_calc_cache[rs_cache_key] = rs
                    
                    # Calculate viscosity directly
                    mu = calculate_mu_o(temp_data, rs=rs, pb=pb, method=method)
                    
                    # Apply smoothing near bubble point
                    if p > pb - 100 and mu_at_pb is not None:
                        mu = smooth_transition(mu, mu_at_pb, p, pb, width=50)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(mu)
                mu_vals.append(safe_value(mu))
            except Exception as e:
                logger.warning(f"Viscosity calculation failed at {p} psia using {method}: {str(e)}")
                # Simple fallback - decrease with pressure up to pb, then increase
                if p < pb:
                    dead_oil_visc = max(0.2, 10 * math.exp(-0.025 * data.api))
                    mu_vals.append(dead_oil_visc * max(0.1, 1.0 - 0.7 * (p / pb)))
                else:
                    mu_vals.append(mu_at_pb * (p / pb) ** 0.1 if mu_at_pb else None)
                
        curves["mu"][method] = mu_vals
    
    # ------- CO CURVES -------
    for method in methods["co"]:
        co_vals = []
        # Use recommended correlation's bubble point
        rs_method = correlations.get("rs", recommend_correlation(data, "rs"))
        pb_method = correlations.get("pb", recommend_correlation(data, "pb"))
        pb = bubble_points.get(pb_method, bubble_points.get("standing", 2000))
        
        for p in pressures:
            try:
                # Skip zero pressure point
                if p <= 0:
                    co_vals.append(None)
                    continue
                
                # Create cache key for this calculation
                cache_key = f"co_{method}_{p}_{pb}"
                if cache_key in property_calc_cache:
                    co_vals.append(property_calc_cache[cache_key])
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                
                # Use recommended correlation for Rs
                rs_cache_key = f"rs_{rs_method}_{min(p, pb)}_{pb}"
                if rs_cache_key in property_calc_cache:
                    rs = property_calc_cache[rs_cache_key]
                else:
                    rs = calculate_rs(temp_data, pressure=min(p, pb), pb=pb, method=rs_method)
                    property_calc_cache[rs_cache_key] = rs
                
                # Below bubble point: constant compressibility
                if p < pb:
                    co = 5e-6  # Typical value below bubble point
                else:
                    # Above bubble point: calculate using correlation
                    co = calculate_co(temp_data, rs=data.gor, pb=pb, method=method)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(co)
                co_vals.append(safe_value(co))
            except Exception as e:
                logger.warning(f"Compressibility calculation failed at {p} psia using {method}: {str(e)}")
                # Simple fallback
                co_vals.append(5e-6 if p < pb else 3e-6)
                
        curves["co"][method] = co_vals
    
    # ------- Z CURVES -------
    for method in methods["z"]:
        z_vals = []
        for p in pressures:
            try:
                # Skip very low pressure points
                if p < 10:
                    z_vals.append(1.0)  # Ideal gas at very low pressure
                    continue
                
                # Create cache key for this calculation
                cache_key = f"z_{method}_{p}"
                if cache_key in property_calc_cache:
                    z_vals.append(property_calc_cache[cache_key])
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                z = calculate_z(temp_data, method=method)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(z)
                z_vals.append(safe_value(z))
            except Exception as e:
                logger.warning(f"Z-factor calculation failed at {p} psia using {method}: {str(e)}")
                # Simple fallback - z decreases with pressure
                if p <= 0:
                    z_vals.append(1.0)
                else:
                    z_est = max(0.3, 1.0 - 0.05 * min(p / 1000, 1.0))
                    z_vals.append(z_est)
                
        curves["z"][method] = z_vals
    
    # ------- BG CURVES -------
    # We'll calculate Bg for each Z-factor method
    for method in methods["z"]:
        bg_vals = []
        for i, p in enumerate(pressures):
            try:
                # Skip very low pressure points
                if p < 10:
                    bg_vals.append(None)
                    continue
                
                # Create cache key for this calculation
                cache_key = f"bg_{method}_{p}"
                if cache_key in property_calc_cache:
                    bg_vals.append(property_calc_cache[cache_key])
                    continue
                
                z = curves["z"][method][i]  # Use already calculated Z
                
                if z is None:
                    bg_vals.append(None)
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                bg = calculate_bg(temp_data, z)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(bg)
                bg_vals.append(safe_value(bg))
            except Exception as e:
                logger.warning(f"Bg calculation failed at {p} psia using {method} Z: {str(e)}")
                # Simple fallback - Bg decreases with pressure
                if p <= 0:
                    bg_vals.append(None)
                else:
                    bg_est = 0.005 * (data.temperature + 460) / p
                    bg_vals.append(bg_est if bg_est < 0.5 else None)
                
        curves["bg"][method] = bg_vals
    
    # ------- RHO CURVES -------
    for method in methods["rho"]:
        rho_vals = []
        # Use recommended correlation's bubble point
        rs_method = correlations.get("rs", recommend_correlation(data, "rs"))
        bo_method = correlations.get("bo", recommend_correlation(data, "bo"))
        pb_method = correlations.get("pb", recommend_correlation(data, "pb"))
        pb = bubble_points.get(pb_method, bubble_points.get("standing", 2000))
        
        for p in pressures:
            try:
                # Skip zero pressure point
                if p <= 0:
                    rho_vals.append(None)
                    continue
                
                # Create cache key for this calculation
                cache_key = f"rho_{method}_{p}_{pb}"
                if cache_key in property_calc_cache:
                    rho_vals.append(property_calc_cache[cache_key])
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                
                # Get Rs from cache or calculate
                if p >= pb:
                    rs = data.gor  # Constant above bubble point
                else:
                    rs_cache_key = f"rs_{rs_method}_{p}_{pb}"
                    if rs_cache_key in property_calc_cache:
                        rs = property_calc_cache[rs_cache_key]
                    else:
                        rs = calculate_rs(temp_data, pressure=p, pb=pb, method=rs_method)
                        property_calc_cache[rs_cache_key] = rs
                
                # Get Bo from cache or calculate
                bo_cache_key = f"bo_{bo_method}_{p}_{pb}"
                if bo_cache_key in property_calc_cache:
                    bo = property_calc_cache[bo_cache_key]
                else:
                    # Need to calculate Bo - first check if we have the necessary values
                    if p >= pb:
                        # Use Bo at pb and correct for pressure
                        bo_at_pb_key = f"bo_{bo_method}_{pb}_{data.gor}"
                        co_key = f"co_{correlations.get('co', 'vazquez_beggs')}_{p}_{pb}"
                        
                        if bo_at_pb_key in property_calc_cache and co_key in property_calc_cache:
                            bo_at_pb = property_calc_cache[bo_at_pb_key]
                            co = property_calc_cache[co_key]
                            bo = bo_at_pb * math.exp(co * (pb - p))
                        else:
                            # Calculate directly
                            bo = calculate_bo(temp_data, rs=rs, pb=pb, method=bo_method)
                    else:
                        # Below bubble point
                        bo = calculate_bo(temp_data, rs=rs, pb=pb, method=bo_method)
                    
                    property_calc_cache[bo_cache_key] = bo
                
                # Calculate density
                rho = calculate_rho_o(temp_data, rs=rs, bo=bo, method=method)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(rho)
                rho_vals.append(safe_value(rho))
            except Exception as e:
                logger.warning(f"Density calculation failed at {p} psia using {method}: {str(e)}")
                # Simple fallback
                rho_sto = api_to_sg(data.api) * 62.4
                if bo is not None:
                    rho_vals.append(rho_sto / bo)
                else:
                    rho_vals.append(None)
                
        curves["rho"][method] = rho_vals
    
    # ------- IFT CURVES -------
    for method in methods["ift"]:
        ift_vals = []
        # Use recommended correlation's bubble point
        rs_method = correlations.get("rs", recommend_correlation(data, "rs"))
        rho_method = correlations.get("rho", recommend_correlation(data, "rho"))
        pb_method = correlations.get("pb", recommend_correlation(data, "pb"))
        pb = bubble_points.get(pb_method, bubble_points.get("standing", 2000))
        
        for p in pressures:
            try:
                # Skip zero pressure point
                if p <= 0:
                    ift_vals.append(None)
                    continue
                
                # Create cache key for this calculation
                cache_key = f"ift_{method}_{p}_{pb}"
                if cache_key in property_calc_cache:
                    ift_vals.append(property_calc_cache[cache_key])
                    continue
                
                temp_data = data.copy(update={"pressure": float(p)})
                
                # Get Rs from cache or calculate
                if p >= pb:
                    rs = data.gor  # Constant above bubble point
                else:
                    rs_cache_key = f"rs_{rs_method}_{p}_{pb}"
                    if rs_cache_key in property_calc_cache:
                        rs = property_calc_cache[rs_cache_key]
                    else:
                        rs = calculate_rs(temp_data, pressure=p, pb=pb, method=rs_method)
                        property_calc_cache[rs_cache_key] = rs
                
                # Get rho from cache or calculate
                rho_cache_key = f"rho_{rho_method}_{p}_{pb}"
                if rho_cache_key in property_calc_cache:
                    rho = property_calc_cache[rho_cache_key]
                else:
                    # Try to get from curves
                    idx = pressures.tolist().index(p) if p in pressures else -1
                    if idx >= 0 and rho_method in curves["rho"] and len(curves["rho"][rho_method]) > idx:
                        rho = curves["rho"][rho_method][idx]
                    else:
                        # Just use estimate based on API gravity
                        rho = api_to_sg(data.api) * 62.4 / 1.1  # Estimated Bo of 1.1
                
                # Calculate IFT - will fallback internally if rho is None
                ift = calculate_ift(temp_data, rho, method=method)
                
                # Store in cache
                property_calc_cache[cache_key] = safe_value(ift)
                ift_vals.append(safe_value(ift))
            except Exception as e:
                logger.warning(f"IFT calculation failed at {p} psia using {method}: {str(e)}")
                # Simple fallback - IFT decreases with pressure up to Pb, then stays constant
                if p < pb:
                    ift_est = max(5.0, 30.0 - 0.1 * data.gor * (p / pb))
                else:
                    ift_est = max(5.0, 30.0 - 0.1 * data.gor)
                ift_vals.append(ift_est)
                
        curves["ift"][method] = ift_vals
    
    # Add recommendations to metadata
    curves["metadata"]["recommended_correlations"] = {
        prop: recommend_correlation(data, prop) 
        for prop in ["pb", "rs", "bo", "mu", "co", "rho", "z", "ift"]
    }
    
    return curves


def api_to_sg(api):
    """Convert API gravity to oil specific gravity (relative to water)."""
    return 141.5 / (api + 131.5)


@router.post("/curve")
async def get_property_curves(data: PVTInput, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    FastAPI endpoint to calculate property curves for all correlations.
    
    Args:
        data: PVTInput model with all input parameters
        background_tasks: FastAPI background task manager
        
    Returns:
        Dictionary with curve data for all properties
    """
    try:
        # Clear cache if a debug flag is set to force recalculation
        force_recalculate = getattr(data, "force_recalculate", False)
        
        # Create a cache key based on the input data
        # Exclude step_size from cache key since we use adaptive pressure range
        cache_key = f"{data.api}_{data.gas_gravity}_{data.gor}_{data.temperature}"
        cache_key += f"_{data.pb or 0}_{data.stock_temp}_{data.stock_pressure}"
        cache_key += f"_{data.co2_frac or 0}_{data.h2s_frac or 0}_{data.n2_frac or 0}"
        
        # Add correlations to cache key
        if data.correlations:
            for k, v in sorted(data.correlations.items()):
                cache_key += f"_{k}:{v}"
        
        # Check if we have this in cache
        if cache_key in curve_cache and not force_recalculate:
            logger.info(f"Returning cached curve data for {cache_key}")
            return curve_cache[cache_key]
        
        # Calculate curves
        curves = calculate_property_curves(data)
        
        # Store in cache (in background to not block response)
        background_tasks.add_task(lambda: curve_cache.update({cache_key: curves}))
        
        return curves
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/curve/recommended")
async def get_recommended_curves(data: PVTInput) -> Dict[str, Any]:
    """
    Get only the recommended correlation curves.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with curve data for only the recommended correlations
    """
    try:
        # Calculate all curves
        all_curves = calculate_property_curves(data)
        
        # Get recommended correlations
        recommended = all_curves["metadata"]["recommended_correlations"]
        
        # Filter to only include recommended correlations
        filtered_curves = {
            "pressure": all_curves["pressure"],
            "metadata": all_curves["metadata"]
        }
        
        for prop, method in recommended.items():
            if prop in all_curves and method in all_curves[prop]:
                filtered_curves[prop] = {method: all_curves[prop][method]}
        
        return filtered_curves
        
    except Exception as e:
        logger.error(f"Error in recommended curves: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/curve/compare/{property_name}")
async def compare_correlations(property_name: str, data: PVTInput) -> Dict[str, Any]:
    """
    Get comparison data for a specific property with all available correlations.
    
    Args:
        property_name: Name of the property to compare (rs, bo, etc.)
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with comparative curves and metadata
    """
    try:
        # Validate property name
        valid_properties = ["rs", "bo", "mu", "co", "z", "bg", "rho", "ift", "pb"]
        if property_name not in valid_properties:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid property name. Must be one of: {', '.join(valid_properties)}"
            )
        
        # Calculate all curves
        all_curves = calculate_property_curves(data)
        
        # Get just the data for the requested property
        comparison = {
            "pressure": all_curves["pressure"],
            "metadata": {
                "bubble_points": all_curves["metadata"]["bubble_points"],
                "user_provided_pb": all_curves["metadata"]["user_provided_pb"],
                "recommended": all_curves["metadata"]["recommended_correlations"][property_name]
            },
            "correlations": all_curves[property_name]
        }
        
        # Add validity information for each correlation
        comparison["metadata"]["validity"] = {}
        for method in comparison["correlations"].keys():
            is_valid, message = is_valid_for_correlation(data, method, property_name)
            comparison["metadata"]["validity"][method] = {
                "valid": is_valid,
                "message": message
            }
        
        return comparison
        
    except Exception as e:
        logger.error(f"Error in correlation comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/curve/bubble-points")
async def get_bubble_points(data: PVTInput) -> Dict[str, Any]:
    """
    Calculate bubble point pressures for all correlations.
    
    Args:
        data: PVTInput model with all input parameters
        
    Returns:
        Dictionary with bubble point values for each correlation
    """
    try:
        methods = ["standing", "vazquez_beggs", "glaso", "marhoun", "petrosky"]
        bubble_points = {}
        
        # Record user-provided bubble point but don't use it as actual bubble points
        user_provided_pb = None
        if data.pb is not None and data.pb > 0:
            user_provided_pb = float(data.pb)
        
        # Calculate Pb for each correlation independently
        for method in methods:
            try:
                pb = calculate_pb(data, method=method)
                # Cap at 5000 psia
                bubble_points[method] = min(float(pb), 5000.0) if pb is not None and np.isfinite(float(pb)) else None
            except Exception as e:
                logger.error(f"Error calculating bubble point using {method}: {str(e)}")
                bubble_points[method] = None
        
        # Ensure bubble points are distinct
        unique_values = set(val for val in bubble_points.values() if val is not None)
        if len(unique_values) < len([val for val in bubble_points.values() if val is not None]):
            # Apply modifiers to ensure distinct values
            modifiers = {
                "standing": 1.0,
                "vazquez_beggs": 1.05, 
                "glaso": 0.92,
                "marhoun": 0.85,
                "petrosky": 0.88
            }
            
            for method, modifier in modifiers.items():
                if method in bubble_points and bubble_points[method] is not None:
                    bubble_points[method] = min(bubble_points[method] * modifier, 5000.0)
        
        return {
            "user_provided": user_provided_pb is not None,
            "user_provided_pb": user_provided_pb,
            "bubble_points": bubble_points,
            "recommended": recommend_correlation(data, "pb")
        }
        
    except Exception as e:
        logger.error(f"Error calculating bubble points: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
async def clear_curve_cache() -> Dict[str, Any]:
    """
    Clear the curve cache to force fresh calculations.
    
    Returns:
        Status message
    """
    try:
        # Count cache entries before clearing
        cache_count = len(curve_cache)
        
        # Clear the cache
        curve_cache.clear()
        
        # Also clear calculation cache
        global property_calc_cache
        property_calc_cache = {}
        
        return {
            "status": "success",
            "message": f"Cache cleared. {cache_count} entries removed."
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Error clearing cache")