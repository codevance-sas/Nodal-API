# app/services/ipr/engine.py
import numpy as np
import logging

logger = logging.getLogger(__name__)

def calculate_ipr_curve(data):
    """
    Calculate the Inflow Performance Relationship (IPR) curve using Modified Vogel Method
    
    Args:
        data: IPRInput model with all parameters
        
    Returns:
        Dictionary with IPR curve data, nodal points, and other calculated values
    """
    BOPD, BWPD, MCFD = data.BOPD, data.BWPD, data.MCFD
    Pr, Pb, PIP = data.Pr, data.Pb or 0, data.PIP
    base_gor = MCFD * 1000 / BOPD if BOPD > 0 else 0

    # If bubble point not provided, estimate it
    if not Pb or Pb <= 0:
        Pb = min(Pr * 0.8, 2500)  # Default estimate
        logger.info(f"No bubble point pressure provided, using estimate: {Pb} psia")

    if PIP > Pb:
        J_oil = BOPD / (Pr - PIP) if (Pr - PIP) > 0 else 0
        J_water = BWPD / (Pr - PIP) if (Pr - PIP) > 0 else 0
    else:
        f = Pb / 1.8 * (1 - 0.2 * PIP / Pb - 0.8 * (PIP / Pb) ** 2)
        J_oil = BOPD / (Pr - Pb + f) if (Pr - Pb + f) > 0 else 0
        J_water = BWPD / (Pr - Pb + f) if (Pr - Pb + f) > 0 else 0

    f = Pb / 1.8
    Qo_max = J_oil * (Pr - Pb + f)
    Qb_oil = J_oil * (Pr - Pb)
    Qw_max = J_water * (Pr - Pb + f)
    Qb_water = J_water * (Pr - Pb)

    # Generate pressure points
    pressures = np.linspace(Pr, 50, data.steps)
    ipr_curve = []
    nodal_points = []

    for Pwf in pressures:
        if Pwf >= Pb:
            Qo = J_oil * (Pr - Pwf)
            Qw = J_water * (Pr - Pwf)
        else:
            factor = 1 - 0.2 * Pwf / Pb - 0.8 * (Pwf / Pb) ** 2
            Qo = (Qo_max - Qb_oil) * factor + Qb_oil
            Qw = (Qw_max - Qb_water) * factor + Qb_water

        if Pwf < 2200:
            new_GOR = (10 ** (3.32 * np.exp(-6.3e-5 * Pwf))) / 800 * base_gor
        else:
            new_GOR = base_gor

        Qg = (new_GOR * Qo) / 1000 if Qo > 0 else 0

        # Add to IPR curve
        ipr_curve.append({
            "pressure": round(Pwf, 2),
            "rate": round(Qo, 2)
        })
        
        # Add to nodal points (with more details)
        nodal_points.append({
            "Pwf": round(Pwf, 2),
            "Qo": round(Qo, 2),
            "Qw": round(Qw, 2),
            "Qg": round(Qg, 2),
            "GVF": round(Qg / (Qo + Qw) * 100, 2) if (Qo + Qw) > 0 else 0
        })

    # Calculate test point PI
    PI = round(BOPD / (Pr - PIP) if (Pr - PIP) > 0 else 0, 3)
    
    # Return the results
    return {
        "ipr_curve": ipr_curve,
        "nodal_points": nodal_points,
        "productivity_index": PI,
        "params": {
            "BOPD": BOPD,
            "BWPD": BWPD,
            "MCFD": MCFD,
            "Pr": Pr,
            "Pb": Pb,
            "PIP": PIP,
            "GOR": base_gor
        }
    }

def get_example_input():
    """
    Return an example input for the IPR calculation
    """
    return {
        "BOPD": 300,
        "BWPD": 1000,
        "MCFD": 500,
        "Pr": 3000,
        "Pb": 2500,
        "PIP": 1800,
        "steps": 25
    }