# backend/pvt/gas_props.py
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