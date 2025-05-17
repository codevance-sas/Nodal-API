# backend/app/services/pvt/gas_props.py
import math
import numpy as np
import logging
from app.utils.conversions import sutton_tpc, sutton_ppc, to_rankine

logger = logging.getLogger(__name__)

def calculate_z(data, method="sutton"):
    """
    Calculate gas compressibility factor (Z) using various correlations.
    
    Args:
        data: PVTInput object containing pressure and temperature
        method: Correlation method to use ('sutton', 'hall_yarborough', 'papay', 'dranchuk_aboukassem')
        
    Returns:
        Z-factor (dimensionless)
    """
    try:
        # Validate inputs
        if not hasattr(data, 'pressure') or data.pressure is None or data.pressure < 0:
            logger.warning("Invalid pressure for Z-factor calculation")
            return 1.0  # Default to ideal gas
            
        if not hasattr(data, 'temperature') or data.temperature is None or data.temperature <= 0:
            logger.warning("Invalid temperature for Z-factor calculation")
            return 1.0  # Default to ideal gas
            
        if not hasattr(data, 'gas_gravity') or data.gas_gravity is None or data.gas_gravity <= 0:
            logger.warning("Invalid gas gravity for Z-factor calculation")
            return 1.0  # Default to ideal gas
        
        # Convert inputs to proper units and ensure they're floats
        P = float(data.pressure)
        T = to_rankine(float(data.temperature))  # Convert to Rankine
        gas_gravity = float(data.gas_gravity)
        
        # Get pseudo-critical properties
        Tpc = sutton_tpc(gas_gravity)
        Ppc = sutton_ppc(gas_gravity)
        
        # Calculate pseudo-reduced properties
        Tpr = T / Tpc
        Ppr = P / Ppc
        
        # Apply corrections for impurities if available
        if hasattr(data, 'co2_frac') and hasattr(data, 'h2s_frac') and hasattr(data, 'n2_frac'):
            co2 = float(data.co2_frac or 0.0)
            h2s = float(data.h2s_frac or 0.0)
            n2 = float(data.n2_frac or 0.0)
            
            # Wichert-Aziz correction for sour gas
            if co2 > 0 or h2s > 0:
                eps = 120 * (co2 + h2s)**0.9 - 120 * (co2 + h2s)**1.6
                Tpc_corr = Tpc - eps
                Ppc_corr = Ppc * Tpc_corr / (Tpc + h2s * (1 - h2s) * eps)
                
                # Update pseudo-reduced properties
                Tpr = T / Tpc_corr
                Ppr = P / Ppc_corr
        
        # Safety check for invalid pseudo-reduced values
        if Tpr <= 0 or Ppr < 0:
            logger.warning("Invalid pseudo-reduced properties: Tpr={}, Ppr={}".format(Tpr, Ppr))
            return 1.0  # Default to ideal gas
        
        # Very high pressure check - limit Ppr for numerical stability
        if Ppr > 30:
            logger.warning(f"Very high pseudo-reduced pressure: {Ppr}. Limiting to 30.")
            Ppr = 30
            
        # Very low temperature check
        if Tpr < 1.0:
            logger.warning(f"Very low pseudo-reduced temperature: {Tpr}. Limiting to 1.0.")
            Tpr = 1.0
        
        # Calculate Z factor based on selected method
        if method == "hall_yarborough":
            return hall_yarborough_z(Tpr, Ppr)
            
        elif method == "papay":
            return papay_z(Tpr, Ppr)
            
        elif method == "dranchuk_aboukassem":
            return dranchuk_aboukassem_z(Tpr, Ppr)
            
        elif method == "sutton":
            return sutton_z(Tpr, Ppr)
            
        else:
            logger.warning(f"Unknown Z-factor method: {method}. Using Sutton.")
            return sutton_z(Tpr, Ppr)
            
    except Exception as e:
        logger.error(f"Error in Z-factor calculation: {str(e)}")
        return 1.0  # Default to ideal gas behavior


def sutton_z(Tpr, Ppr):
    """
    Calculate Z-factor using Sutton's correlation (DAK equation).
    Improved implementation with safety checks and iteration limits.
    
    Args:
        Tpr: Pseudo-reduced temperature
        Ppr: Pseudo-reduced pressure
        
    Returns:
        Z-factor (dimensionless)
    """
    # Check for trivial cases
    if Ppr < 0.1:
        return 1.0  # Near-ideal gas at very low pressures
    
    # Dranchuk-Abou-Kassem coefficients
    A = [
        0.3265, -1.0700, -0.5339, 0.01569, -0.05165,
        0.5475, -0.7361, 0.1844, 0.1056, 0.6134, 0.7210
    ]
    
    # Initial guess for Z (better than 1.0 for high pressures)
    if Ppr > 5:
        z = 0.5  # Better initial guess for high pressures
    else:
        z = 1.0
    
    # Newton-Raphson iteration with damping and limits
    max_iterations = 100
    tolerance = 1e-6
    damping = 0.7  # Damping factor to avoid oscillations
    
    for i in range(max_iterations):
        # Calculate reduced density
        rho_r = 0.27 * Ppr / (z * Tpr)
        
        # Prevent unreasonable reduced density
        if rho_r > 3.0 or rho_r < 0:
            logger.warning(f"Reduced density out of range: {rho_r} at iteration {i}")
            return max(0.3, min(1.2, 0.27 * Ppr / Tpr))  # Return reasonable estimate
        
        # DAK equation of state
        f = 1 + (A[0] + A[1]/Tpr + A[2]/Tpr**3 + A[3]/Tpr**4 + A[4]/Tpr**5) * rho_r \
              + (A[5] + A[6]/Tpr + A[7]/Tpr**2) * rho_r**2 \
              - A[8] * (A[6]/Tpr + A[7]/Tpr**2) * rho_r**5 \
              + A[9] * (1 + A[10] * rho_r**2) * rho_r**2 * math.exp(-A[10] * rho_r**2) - z
        
        # Derivative for Newton-Raphson method
        df_drho = (A[0] + A[1]/Tpr + A[2]/Tpr**3 + A[3]/Tpr**4 + A[4]/Tpr**5) \
                + 2 * (A[5] + A[6]/Tpr + A[7]/Tpr**2) * rho_r \
                - 5 * A[8] * (A[6]/Tpr + A[7]/Tpr**2) * rho_r**4 \
                + A[9] * (2 * rho_r + 4 * A[10] * rho_r**3) * math.exp(-A[10] * rho_r**2) \
                - A[9] * A[10] * 2 * rho_r**4 * math.exp(-A[10] * rho_r**2)
        
        drho_dz = -0.27 * Ppr / (z**2 * Tpr)
        df_dz = drho_dz * df_drho - 1
        
        # Apply Newton-Raphson update with damping
        delta_z = -f / df_dz
        
        # Limit update step size for stability
        if abs(delta_z) > 0.5:
            delta_z = 0.5 * np.sign(delta_z)
            
        # Apply damping to avoid oscillations
        delta_z *= damping
        
        # Update Z
        z_new = z + delta_z
        
        # Ensure physically reasonable Z value
        if z_new <= 0:
            z_new = 0.05
        
        # Check convergence
        if abs(z_new - z) < tolerance:
            # Ensure final value is physically reasonable
            return max(0.2, min(z_new, 1.5))
        
        # Update for next iteration
        z = z_new
    
    # If didn't converge, return a physically reasonable value
    logger.warning(f"Z-factor calculation didn't converge after {max_iterations} iterations")
    return max(0.2, min(z, 1.5))


def hall_yarborough_z(Tpr, Ppr):
    """
    Calculate Z-factor using Hall-Yarborough correlation.
    
    Args:
        Tpr: Pseudo-reduced temperature
        Ppr: Pseudo-reduced pressure
        
    Returns:
        Z-factor (dimensionless)
    """
    # Check input validity
    if Tpr <= 1.0:
        # Below critical temperature requires special handling
        logger.warning(f"Hall-Yarborough not recommended for Tpr < 1.0: {Tpr}")
        return max(0.4, min(1.2, 1.0 - 0.07 * Ppr))  # Simple approximation
    
    # Hall-Yarborough parameters
    t = 1.0 / Tpr
    A = 0.06125 * Ppr * t * math.exp(-1.2 * (1.0 - t)**2)
    B = 14.76 * t - 9.76 * t**2 + 4.58 * t**3
    C = 90.7 * t - 242.2 * t**2 + 42.4 * t**3
    D = 2.18 + 2.82 * t
    
    # Initial guess for reduced density
    Y = 0.0125 * Ppr * t  # Better initial approximation
    if Y <= 0:
        Y = 0.001  # Fallback
    
    # Newton-Raphson iteration with damping
    max_iterations = 50
    tolerance = 1e-7
    
    for i in range(max_iterations):
        # Function and derivative calculation
        f = -A / Y + (y_term(Y) / y_prime(Y)) - B * Y + C * Y**D
        df = A / Y**2 + (y_second(Y) / y_prime(Y)) - (y_term(Y) * y_third(Y)) / y_prime(Y)**2 - B + C * D * Y**(D-1)
        
        # Newton-Raphson update with safety checks
        if abs(df) < 1e-10:
            # Avoid division by near-zero
            delta_Y = 0.001 * np.sign(f) if f != 0 else 0.001
        else:
            delta_Y = -f / df
            
        # Limit step size
        delta_Y = max(min(delta_Y, 0.1), -0.1)
        
        # Update Y with limits to prevent negative values
        Y_new = max(0.0001, Y + delta_Y)
        
        # Check convergence
        if abs(Y_new - Y) < tolerance:
            break
            
        Y = Y_new
    
    # Calculate Z from final Y
    if Y <= 0 or Y > 1.0:
        logger.warning(f"Hall-Yarborough converged to invalid Y: {Y}")
        Y = min(max(Y, 0.0001), 0.99)
    
    Z = 0.06125 * Ppr * t / Y
    
    # Ensure Z is physically reasonable
    return max(0.2, min(Z, 1.5))


def y_term(Y):
    """Helper function for Hall-Yarborough calculation."""
    return Y + Y**2 + Y**3 - Y**4


def y_prime(Y):
    """First derivative of y_term."""
    return 1.0 + 2.0 * Y + 3.0 * Y**2 - 4.0 * Y**3


def y_second(Y):
    """Second derivative of y_term."""
    return 2.0 + 6.0 * Y - 12.0 * Y**2


def y_third(Y):
    """Third derivative of y_term."""
    return 6.0 - 24.0 * Y


def papay_z(Tpr, Ppr):
    """
    Calculate Z-factor using Papay correlation.
    Simple but accurate for many natural gas applications.
    
    Args:
        Tpr: Pseudo-reduced temperature
        Ppr: Pseudo-reduced pressure
        
    Returns:
        Z-factor (dimensionless)
    """
    # Safety checks
    if Ppr < 0 or Tpr <= 0:
        logger.warning("Invalid inputs for Papay correlation")
        return 1.0
    
    # Papay correlation
    Z = 1.0 - (3.53 * Ppr / (10**0.9813 * Tpr)) * math.exp(-0.27 * Ppr) + (0.274 * Ppr**2 / (10**0.8157 * Tpr)) * math.exp(-0.864 * Ppr)
    
    # Ensure physically reasonable value
    return max(0.2, min(Z, 1.5))


def dranchuk_aboukassem_z(Tpr, Ppr):
    """
    Calculate Z-factor using Dranchuk-Abou-Kassem correlation.
    More detailed implementation than the Sutton method.
    
    Args:
        Tpr: Pseudo-reduced temperature
        Ppr: Pseudo-reduced pressure
        
    Returns:
        Z-factor (dimensionless)
    """
    # Constants for DAK method
    A = [0, 0.3265, -1.0700, -0.5339, 0.01569, -0.05165, 0.5475,
         -0.7361, 0.1844, 0.1056, 0.6134, 0.7210]
    
    # Check validity range
    if Tpr < 1.0 or Tpr > 3.0 or Ppr > 30.0:
        logger.warning(f"DAK used outside validity range: Tpr={Tpr}, Ppr={Ppr}")
    
    # Initial guess based on pressure range
    if Ppr < 1.0:
        z = 1.0  # Low pressure: start with ideal gas
    else:
        z = 0.27 * Ppr / Tpr  # Higher pressure: better initial guess
    
    # Newton-Raphson iteration
    tolerance = 1e-6
    max_iterations = 100
    converged = False
    
    for i in range(max_iterations):
        # Calculate reduced density
        rho_r = 0.27 * Ppr / (z * Tpr)
        
        # Prevent unreasonable reduced density for numerical stability
        if rho_r > 3.0 or rho_r < 0:
            logger.warning(f"DAK reduced density out of range: {rho_r}")
            return max(0.2, min(1.5, 0.27 * Ppr / Tpr))
        
        # Calculate EOS terms
        rho_r2 = rho_r**2
        rho_r5 = rho_r**5
        
        # Core equation terms
        term1 = 1.0
        term2 = A[1] + A[2]/Tpr + A[3]/Tpr**3 + A[4]/Tpr**4 + A[5]/Tpr**5
        term3 = A[6] + A[7]/Tpr + A[8]/Tpr**2
        term4 = A[9] * (A[7]/Tpr + A[8]/Tpr**2)
        term5 = A[10]
        term6 = A[11]
        
        # Function evaluation
        c1 = term1 + term2 * rho_r + term3 * rho_r2 - term4 * rho_r5
        c2 = term5 * rho_r2 * (1.0 + term6 * rho_r2) * math.exp(-term6 * rho_r2)
        z_new = c1 + c2
        
        # Check for convergence
        if abs(z - z_new) < tolerance:
            converged = True
            z = z_new
            break
        
        # Update z with damping for stability
        z = 0.7 * z_new + 0.3 * z
    
    if not converged:
        logger.warning(f"DAK didn't converge after {max_iterations} iterations")
    
    # Ensure physically reasonable Z value
    return max(0.2, min(z, 1.5))


def calculate_bg(data, z=None, method="standard"):
    """
    Calculate gas formation volume factor (Bg).
    
    Args:
        data: PVTInput object
        z: Z-factor (if already calculated)
        method: Method to use (currently only 'standard' is implemented)
        
    Returns:
        Gas formation volume factor (Bg) in RB/SCF
    """
    try:
        # Validate inputs
        if not hasattr(data, 'pressure') or data.pressure is None or data.pressure <= 0:
            logger.warning("Invalid pressure for Bg calculation")
            return 0.005  # Default fallback value
            
        if not hasattr(data, 'temperature') or data.temperature is None or data.temperature <= 0:
            logger.warning("Invalid temperature for Bg calculation")
            return 0.005  # Default fallback value
        
        T = float(data.temperature)
        P = float(data.pressure)
        
        # Calculate Z if not provided
        if z is None:
            z = calculate_z(data)
        
        # Validate Z value
        if z is None or z <= 0:
            logger.warning("Invalid Z-factor for Bg calculation")
            z = 1.0  # Default to ideal gas
        
        # Standard gas FVF equation (in reservoir barrels per SCF)
        bg = 0.00504 * z * (T + 460) / P
        
        # Ensure result is physically reasonable
        if bg <= 0 or bg > 0.5:
            logger.warning(f"Calculated Bg outside normal range: {bg}")
            bg = max(0.0001, min(bg, 0.5))
            
        return bg
        
    except Exception as e:
        logger.error(f"Error in Bg calculation: {str(e)}")
        return 0.005  # Default fallback value


def calculate_cg(data, z=None, method="standard"):
    """
    Calculate gas compressibility (cg).
    
    Args:
        data: PVTInput object
        z: Z-factor (if already calculated)
        method: Method to use (currently only 'standard' is implemented)
        
    Returns:
        Gas compressibility (cg) in 1/psi
    """
    try:
        # Calculate Z if not provided
        if z is None:
            z = calculate_z(data)
        
        # Validate inputs
        if not hasattr(data, 'pressure') or data.pressure is None or data.pressure <= 0:
            logger.warning("Invalid pressure for cg calculation")
            return 1e-3  # Default fallback value
            
        T = float(data.temperature) + 460  # Convert to Rankine
        P = float(data.pressure)
        
        # Calculate pseudo-reduced properties
        gas_gravity = float(data.gas_gravity)
        Tpc = sutton_tpc(gas_gravity)
        Ppc = sutton_ppc(gas_gravity)
        Tpr = T / Tpc
        Ppr = P / Ppc
        
        # Calculate derivative of Z with respect to pressure
        # Using a numerical approximation (central difference)
        delta_p = 0.01 * P  # 1% pressure difference
        
        # Calculate Z at P+ΔP
        data_plus = data.copy(update={"pressure": P + delta_p})
        z_plus = calculate_z(data_plus)
        
        # Calculate Z at P-ΔP
        data_minus = data.copy(update={"pressure": max(1.0, P - delta_p)})
        z_minus = calculate_z(data_minus)
        
        # Central difference approximation of dZ/dP
        dz_dp = (z_plus - z_minus) / (2 * delta_p)
        
        # Gas compressibility equation
        cg = 1/P - (1/z) * dz_dp
        
        # Ensure result is physically reasonable
        if cg <= 0 or cg > 0.1:
            logger.warning(f"Calculated cg outside normal range: {cg}")
            cg = max(1e-5, min(cg, 0.1))
            
        return cg
        
    except Exception as e:
        logger.error(f"Error in cg calculation: {str(e)}")
        return 1e-3  # Default fallback value


def calculate_gas_density(data, z=None, method="standard"):
    """
    Calculate gas density at reservoir conditions.
    
    Args:
        data: PVTInput object
        z: Z-factor (if already calculated)
        method: Method to use (currently only 'standard' is implemented)
        
    Returns:
        Gas density (ρg) in lb/ft³
    """
    try:
        # Calculate Z if not provided
        if z is None:
            z = calculate_z(data)
        
        # Validate inputs
        if not hasattr(data, 'pressure') or data.pressure is None or data.pressure <= 0:
            logger.warning("Invalid pressure for gas density calculation")
            return 0.05  # Default fallback value
            
        if not hasattr(data, 'temperature') or data.temperature is None or data.temperature <= 0:
            logger.warning("Invalid temperature for gas density calculation")
            return 0.05  # Default fallback value
            
        if not hasattr(data, 'gas_gravity') or data.gas_gravity is None or data.gas_gravity <= 0:
            logger.warning("Invalid gas gravity for gas density calculation")
            return 0.05  # Default fallback value
        
        T = float(data.temperature) + 460  # Convert to Rankine
        P = float(data.pressure)
        gas_gravity = float(data.gas_gravity)
        
        # Gas density equation (lb/ft³)
        # ρg = (PM)/(ZRT) where M = 28.97*γg
        R = 10.73  # Gas constant in (psia·ft³)/(lb-mol·°R)
        molecular_weight = 28.97 * gas_gravity
        
        rho_g = (P * molecular_weight) / (z * R * T)
        
        # Ensure result is physically reasonable
        if rho_g <= 0 or rho_g > 50:
            logger.warning(f"Calculated gas density outside normal range: {rho_g}")
            rho_g = max(0.001, min(rho_g, 50))
            
        return rho_g
        
    except Exception as e:
        logger.error(f"Error in gas density calculation: {str(e)}")
        return 0.05  # Default fallback value


def calculate_gas_viscosity(data, z=None, method="lee_gonzalez"):
    """
    Calculate gas viscosity using the Lee-Gonzalez-Eakin correlation.
    
    Args:
        data: PVTInput object
        z: Z-factor (if already calculated)
        method: Viscosity calculation method ('lee_gonzalez' or 'carr')
        
    Returns:
        Gas viscosity (μg) in centipoise (cp)
    """
    try:
        # Validate inputs
        if not hasattr(data, 'pressure') or data.pressure is None or data.pressure <= 0:
            logger.warning("Invalid pressure for gas viscosity calculation")
            return 0.02  # Default fallback value
            
        if not hasattr(data, 'temperature') or data.temperature is None or data.temperature <= 0:
            logger.warning("Invalid temperature for gas viscosity calculation")
            return 0.02  # Default fallback value
            
        if not hasattr(data, 'gas_gravity') or data.gas_gravity is None or data.gas_gravity <= 0:
            logger.warning("Invalid gas gravity for gas viscosity calculation")
            return 0.02  # Default fallback value
        
        T = float(data.temperature) + 460  # Convert to Rankine
        P = float(data.pressure)
        gas_gravity = float(data.gas_gravity)
        
        # Calculate gas density (required for Lee-Gonzalez-Eakin)
        if z is None:
            z = calculate_z(data)
            
        rho_g = calculate_gas_density(data, z)
        
        if method == "lee_gonzalez":
            # Lee-Gonzalez-Eakin correlation (1966)
            # Calculate correlation parameters
            Mw = 28.97 * gas_gravity
            K = (9.4 + 0.02 * Mw) * T**1.5 / (209 + 19 * Mw + T)
            X = 3.5 + 986 / T + 0.01 * Mw
            Y = 2.4 - 0.2 * X
            
            # Calculate viscosity (cp)
            visc = K * 1e-4 * math.exp(X * rho_g**Y)
        
        elif method == "carr":
            # Carr et al. correlation (viscosity ratio method)
            # Calculate atmospheric viscosity first
            visc_atm = 8.188e-3 - 6.15e-3 * math.log10(gas_gravity) + \
                      (1.709e-5 - 2.062e-6 * math.log10(gas_gravity)) * data.temperature
            
            # Calculate viscosity ratio
            if P <= 100:
                # Low pressure formula (P ≤ 100 psia)
                visc_ratio = 1.0 + (0.03 * P + 0.0004 * P**2) / (T / 100.0)**3.4
            else:
                # High pressure formula (P > 100 psia)
                visc_ratio = 0.9 + (0.02 * P + 20000.0 / P) / (T / 100.0)**2
                
            # Calculate final viscosity
            visc = visc_atm * visc_ratio
        
        else:
            # Default to Lee-Gonzalez-Eakin
            logger.warning(f"Unknown viscosity calculation method: {method}")
            Mw = 28.97 * gas_gravity
            K = (9.4 + 0.02 * Mw) * T**1.5 / (209 + 19 * Mw + T)
            X = 3.5 + 986 / T + 0.01 * Mw
            Y = 2.4 - 0.2 * X
            visc = K * 1e-4 * math.exp(X * rho_g**Y)
        
        # Ensure result is physically reasonable
        if visc <= 0 or visc > 0.1:
            logger.warning(f"Calculated gas viscosity outside normal range: {visc}")
            visc = max(0.005, min(visc, 0.1))
            
        return visc
        
    except Exception as e:
        logger.error(f"Error in gas viscosity calculation: {str(e)}")
        return 0.02  # Default fallback value


def calculate_critical_properties(
    gas_gravity: float,
    co2_fraction: float = 0.0,
    h2s_fraction: float = 0.0,
    n2_fraction: float = 0.0
) -> tuple:
    """
    Calculate critical properties of gas mixture using Standing correlation
    with adjustments for non-hydrocarbon components.
    
    Args:
        gas_gravity: Gas specific gravity (air = 1)
        co2_fraction: Mole fraction of CO2
        h2s_fraction: Mole fraction of H2S
        n2_fraction: Mole fraction of N2
        
    Returns:
        Tuple of (critical pressure in psia, critical temperature in °R, correction factor)
    """
    # Base critical properties for hydrocarbon component
    Tpc_hc = sutton_tpc(gas_gravity)
    Ppc_hc = sutton_ppc(gas_gravity)
    
    # Mole fraction of hydrocarbon component
    y_hc = 1.0 - co2_fraction - h2s_fraction - n2_fraction
    
    # Critical properties of non-hydrocarbon components (°R, psia)
    Tc_co2, Pc_co2 = 547.6, 1071.0
    Tc_h2s, Pc_h2s = 672.0, 1306.0
    Tc_n2, Pc_n2 = 227.2, 493.0
    
    # Calculate pseudo-critical properties of the mixture using mixing rules
    Tpc_mix = y_hc * Tpc_hc + co2_fraction * Tc_co2 + h2s_fraction * Tc_h2s + n2_fraction * Tc_n2
    Ppc_mix = y_hc * Ppc_hc + co2_fraction * Pc_co2 + h2s_fraction * Pc_h2s + n2_fraction * Pc_n2
    
    # Wichert-Aziz correction for sour gas
    correction = 0.0
    if co2_fraction > 0 or h2s_fraction > 0:
        sour_fraction = co2_fraction + h2s_fraction
        correction = 120 * (sour_fraction**0.9 - sour_fraction**1.6)
        Tpc_corr = Tpc_mix - correction
        Ppc_corr = Ppc_mix * Tpc_corr / (Tpc_mix + h2s_fraction * (1 - h2s_fraction) * correction)
        return Ppc_corr, Tpc_corr, correction
    
    return Ppc_mix, Tpc_mix, correction


def calculate_joule_thomson_coefficient(data, z=None):
    """
    Calculate Joule-Thomson coefficient for natural gas.
    This coefficient represents the rate of temperature change with pressure
    during an isenthalpic expansion process.
    
    Args:
        data: PVTInput object
        z: Z-factor (if already calculated)
        
    Returns:
        Joule-Thomson coefficient in °F/psia
    """
    try:
        # Validate inputs
        if not hasattr(data, 'pressure') or data.pressure is None or data.pressure <= 0:
            logger.warning("Invalid pressure for JT coefficient calculation")
            return 0.01  # Default fallback value
            
        if not hasattr(data, 'temperature') or data.temperature is None or data.temperature <= 0:
            logger.warning("Invalid temperature for JT coefficient calculation")
            return 0.01  # Default fallback value
            
        if not hasattr(data, 'gas_gravity') or data.gas_gravity is None or data.gas_gravity <= 0:
            logger.warning("Invalid gas gravity for JT coefficient calculation")
            return 0.01  # Default fallback value
        
        T = float(data.temperature) + 460  # Convert to Rankine
        P = float(data.pressure)
        gas_gravity = float(data.gas_gravity)
        
        # Calculate Z if not provided
        if z is None:
            z = calculate_z(data)
            
        # Get pseudo-critical properties
        Tpc = sutton_tpc(gas_gravity)
        Ppc = sutton_ppc(gas_gravity)
        
        # Calculate pseudo-reduced properties
        Tpr = T / Tpc
        Ppr = P / Ppc
        
        # Calculate derivatives of Z with respect to P and T
        # Using numerical approximation (central differences)
        delta_p = 0.01 * P  # 1% pressure difference
        delta_t = 5.0       # 5°R temperature difference
        
        # Calculate Z at different conditions for derivatives
        data_p_plus = data.copy(update={"pressure": P + delta_p})
        z_p_plus = calculate_z(data_p_plus)
        
        data_p_minus = data.copy(update={"pressure": max(1.0, P - delta_p)})
        z_p_minus = calculate_z(data_p_minus)
        
        data_t_plus = data.copy(update={"temperature": (T + delta_t - 460)})
        z_t_plus = calculate_z(data_t_plus)
        
        data_t_minus = data.copy(update={"temperature": max(40.0, T - delta_t - 460)})
        z_t_minus = calculate_z(data_t_minus)
        
        # Calculate derivatives
        dz_dp = (z_p_plus - z_p_minus) / (2 * delta_p)
        dz_dt = (z_t_plus - z_t_minus) / (2 * delta_t)
        
        # Calculate specific heat ratio (k) - using approximation
        k = 1.28 - 0.01 * gas_gravity  # Approximation for natural gas
        
        # Calculate specific heat at constant pressure (cp)
        # This is a simplified model, more accurate would require real gas properties
        # cp in BTU/(lb-°R)
        cp = (k / (k - 1)) * (1.987 / 28.97 / gas_gravity)  # Approximate for natural gas
        
        # Calculate Joule-Thomson coefficient
        # μJT = (1/cp) * [T*(∂Z/∂T)P - Z] / [P*(∂Z/∂P)T]
        term1 = T * dz_dt - z
        term2 = P * dz_dp
        
        if abs(term2) < 1e-10:
            # Avoid division by near-zero
            jt_coef = 0.01  # Default value
        else:
            jt_coef = (1.0 / cp) * (term1 / term2)
        
        # Convert to °F/psia if needed
        # jt_coef is already in correct units
        
        # Ensure result is physically reasonable
        if jt_coef < -0.1 or jt_coef > 0.1:
            logger.warning(f"Calculated JT coefficient outside normal range: {jt_coef}")
            jt_coef = max(-0.1, min(jt_coef, 0.1))
            
        return jt_coef
        
    except Exception as e:
        logger.error(f"Error in Joule-Thomson coefficient calculation: {str(e)}")
        return 0.01  # Default fallback value


def calculate_hydrate_formation_temperature(
    pressure: float,
    gas_gravity: float,
    co2_fraction: float = 0.0,
    h2s_fraction: float = 0.0,
    n2_fraction: float = 0.0
) -> float:
    """
    Calculate hydrate formation temperature for natural gas using the
    simplified Katz correlation.
    
    Args:
        pressure: Gas pressure in psia
        gas_gravity: Gas specific gravity (air = 1)
        co2_fraction: Mole fraction of CO2
        h2s_fraction: Mole fraction of H2S
        n2_fraction: Mole fraction of N2
        
    Returns:
        Hydrate formation temperature in °F
    """
    try:
        # Validate inputs
        if pressure <= 0:
            logger.warning("Invalid pressure for hydrate formation calculation")
            return 32.0  # Default to freezing point
        
        if gas_gravity <= 0:
            logger.warning("Invalid gas gravity for hydrate formation calculation")
            return 32.0
        
        # Base temperature correlation for sweet gas
        # Using modified Katz correlation
        if pressure < 100:
            temp = 33.0 + 0.2 * pressure - 16.0 * gas_gravity
        elif pressure < 500:
            temp = 40.0 + 0.1 * pressure - 15.0 * gas_gravity
        elif pressure < 1000:
            temp = 47.0 + 0.08 * pressure - 13.0 * gas_gravity
        elif pressure < 2000:
            temp = 58.0 + 0.05 * pressure - 10.0 * gas_gravity
        elif pressure < 3000:
            temp = 65.0 + 0.035 * pressure - 8.0 * gas_gravity
        else:
            temp = 70.0 + 0.025 * pressure - 5.0 * gas_gravity
        
        # Adjustments for non-hydrocarbon components
        # CO2 and H2S promote hydrate formation, N2 inhibits
        temp += 10.0 * co2_fraction + 15.0 * h2s_fraction - 8.0 * n2_fraction
        
        # Ensure result is physically reasonable
        temp = max(0.0, min(temp, 100.0))
        
        return temp
        
    except Exception as e:
        logger.error(f"Error in hydrate formation temperature calculation: {str(e)}")
        return 32.0  # Default to freezing point


def real_gas_pseudopressure(
    p_range: list,
    data,
    num_points: int = 20
) -> dict:
    """
    Calculate real gas pseudopressure (m(p)) for gas reservoir analysis.
    This is particularly important for gas well deliverability calculations.
    
    Args:
        p_range: List [p_min, p_max] with pressure range to evaluate
        data: PVTInput object with gas properties
        num_points: Number of points for integration
        
    Returns:
        Dictionary with pressure values and corresponding pseudopressures
    """
    try:
        # Validate inputs
        if len(p_range) != 2 or p_range[0] < 0 or p_range[1] <= p_range[0]:
            logger.warning("Invalid pressure range for pseudopressure calculation")
            return {"pressures": [14.7, 1000], "pseudopressures": [0, 0]}
        
        p_min, p_max = p_range
        
        # Create pressure points for evaluation
        pressures = np.linspace(p_min, p_max, num_points)
        
        # Initialize arrays
        z_values = np.zeros(num_points)
        visc_values = np.zeros(num_points)
        mp_values = np.zeros(num_points)
        
        # Calculate properties at each pressure
        for i, p in enumerate(pressures):
            # Create data object with updated pressure
            data_at_p = data.copy(update={"pressure": float(p)})
            
            # Calculate Z-factor
            z_values[i] = calculate_z(data_at_p)
            
            # Calculate viscosity
            visc_values[i] = calculate_gas_viscosity(data_at_p, z_values[i])
        
        # Calculate pseudopressure
        # m(p) = 2∫(p/μZ)dp
        # Using trapezoidal integration
        for i in range(num_points):
            if i == 0:
                mp_values[i] = 0  # Reference point
            else:
                # Integrand: 2 * p / (μ * Z)
                y_prev = 2 * pressures[i-1] / (visc_values[i-1] * z_values[i-1])
                y_curr = 2 * pressures[i] / (visc_values[i] * z_values[i])
                
                # Trapezoidal rule
                dp = pressures[i] - pressures[i-1]
                mp_values[i] = mp_values[i-1] + 0.5 * (y_prev + y_curr) * dp
        
        # Ensure results are physically reasonable
        if np.any(np.isnan(mp_values)) or np.any(np.isinf(mp_values)):
            logger.warning("NaN or Inf values detected in pseudopressure calculation")
            mp_values = np.nan_to_num(mp_values, nan=0.0, posinf=1e10, neginf=0.0)
        
        return {
            "pressures": pressures.tolist(),
            "pseudopressures": mp_values.tolist(),
            "z_values": z_values.tolist(),
            "viscosities": visc_values.tolist()
        }
        
    except Exception as e:
        logger.error(f"Error in real gas pseudopressure calculation: {str(e)}")
        return {"pressures": [14.7, 1000], "pseudopressures": [0, 0]}


def calculate_adiabatic_temperature_change(
    inlet_pressure: float,
    outlet_pressure: float,
    inlet_temperature: float,
    gas_gravity: float,
    efficiency: float = 0.75,
    k: float = None
) -> float:
    """
    Calculate temperature change during adiabatic compression/expansion.
    Important for gas compression calculations.
    
    Args:
        inlet_pressure: Initial gas pressure in psia
        outlet_pressure: Final gas pressure in psia
        inlet_temperature: Initial gas temperature in °F
        gas_gravity: Gas specific gravity (air = 1)
        efficiency: Adiabatic efficiency (for compressors)
        k: Specific heat ratio (cp/cv), calculated if None
        
    Returns:
        Final temperature in °F
    """
    try:
        # Validate inputs
        if inlet_pressure <= 0 or outlet_pressure <= 0:
            logger.warning("Invalid pressure for adiabatic temperature calculation")
            return inlet_temperature
            
        # Convert temperature to Rankine
        inlet_temp_r = inlet_temperature + 460
        
        # Calculate specific heat ratio if not provided
        if k is None:
            # Estimate k based on gas gravity
            k = 1.32 - 0.0055 * gas_gravity
        
        # Pressure ratio
        ratio = outlet_pressure / inlet_pressure
        
        # Calculate temperature change
        # T₂ = T₁ * (P₂/P₁)^((k-1)/(k*η)) for compression (ratio > 1)
        # T₂ = T₁ * (P₂/P₁)^((k-1)/(k)) * η for expansion (ratio < 1)
        if ratio > 1:  # Compression
            outlet_temp_r = inlet_temp_r * ratio**((k-1)/(k*efficiency))
        else:  # Expansion
            outlet_temp_r = inlet_temp_r * ratio**((k-1)/k) * efficiency
        
        # Convert back to °F
        outlet_temp_f = outlet_temp_r - 460
        
        # Ensure result is physically reasonable
        if outlet_temp_f < -100 or outlet_temp_f > 1000:
            logger.warning(f"Calculated temperature outside normal range: {outlet_temp_f}")
            outlet_temp_f = max(-100, min(outlet_temp_f, 1000))
            
        return outlet_temp_f
        
    except Exception as e:
        logger.error(f"Error in adiabatic temperature calculation: {str(e)}")
        return inlet_temperature