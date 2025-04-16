from typing import List, Optional, Dict, Any
import numpy as np
import logging
import math

from app.schemas.pvt import PVTInput, PVTResult
from app.services.pvt.gas_props import calculate_z, calculate_bg
from app.services.pvt.oil_props import (
    calculate_pb,
    calculate_rs,
    calculate_bo,
    calculate_mu_o,
    calculate_co,
    calculate_rho_o,
    recommend_correlation
)
from .ift import calculate_ift

logger = logging.getLogger(__name__)

def validate_input(data: PVTInput) -> Dict[str, Any]:
    messages = {"errors": [], "warnings": []}

    if not data.api or data.api <= 0:
        messages["errors"].append("API gravity must be provided and greater than 0")
    elif data.api < 5 or data.api > 70:
        messages["warnings"].append(f"API gravity of {data.api} is outside typical range (5-70)")

    if not data.gas_gravity or data.gas_gravity <= 0:
        messages["errors"].append("Gas specific gravity must be provided and greater than 0")
    elif data.gas_gravity < 0.55 or data.gas_gravity > 1.5:
        messages["warnings"].append(f"Gas gravity of {data.gas_gravity} is outside typical range (0.55-1.5)")

    if not data.gor or data.gor < 0:
        messages["errors"].append("Measured GOR must be provided and non-negative")
    elif data.gor > 5000:
        messages["warnings"].append(f"GOR of {data.gor} SCF/STB is unusually high")

    if not data.temperature or data.temperature <= 0:
        messages["errors"].append("Reservoir temperature must be provided and greater than 0°F")
    elif data.temperature < 60 or data.temperature > 350:
        messages["warnings"].append(f"Reservoir temperature of {data.temperature}°F is outside typical range (60-350°F)")

    if data.pb is not None and data.pb <= 0:
        messages["errors"].append("Bubble point pressure must be greater than 0 psia if provided")

    if data.step_size is not None and data.step_size <= 0:
        messages["warnings"].append(f"Invalid step size {data.step_size}. Using default 25 psi")

    total_fraction = (data.co2_frac or 0) + (data.h2s_frac or 0) + (data.n2_frac or 0)
    if total_fraction > 1.0:
        messages["errors"].append(f"Total gas impurity fractions ({total_fraction:.4f}) exceed 1.0")

    return messages

def generate_pressure_range(data: PVTInput, pb: float) -> np.ndarray:
    step = data.step_size or 25
    pb_rounded = round(pb / step) * step
    MAX_PRESSURE = 10000
    max_pressure = min(MAX_PRESSURE, max(5000, round(2.0 * pb / step) * step))

    lower_step = step * 2
    p_lower = np.arange(0, 0.9 * pb_rounded, lower_step)
    pb_segment_step = step / 2
    p_critical = np.arange(0.9 * pb_rounded, 1.1 * pb_rounded, pb_segment_step)
    p_upper = np.arange(1.1 * pb_rounded, max_pressure + step, step)

    pressures = np.unique(np.concatenate([p_lower, p_critical, p_upper]))
    if pb not in pressures:
        pressures = np.sort(np.append(pressures, pb))

    return pressures

def calculate_pvt(data: PVTInput) -> Dict[str, Any]:
    validation = validate_input(data)
    if validation["errors"]:
        return {"status": "error", "messages": validation["errors"], "results": None}

    corr = data.correlations or {}
    for prop in ["pb", "rs", "bo", "mu", "co", "rho", "z", "ift"]:
        if prop not in corr:
            corr[prop] = recommend_correlation(data, prop)

    try:
        if hasattr(data, "pb") and data.pb is not None and data.pb > 0:
            pb = float(data.pb)
            logger.info(f"Using provided bubble point pressure: {pb:.2f} psia")
        else:
            pb = calculate_pb(data, method=corr["pb"])
            if pb is None or not np.isfinite(float(pb)) or pb <= 0:
                pb = min(max(14.7, data.gor * 5), 5000)
                logger.warning(f"Bubble point calculation failed, using fallback: {pb:.2f} psia")
            else:
                logger.info(f"Calculated bubble point pressure: {pb:.2f} psia using {corr['pb']} correlation")
    except Exception as e:
        logger.error(f"Failed to calculate bubble point: {str(e)}")
        pb = min(max(14.7, data.gor * 5), 5000)
        logger.warning(f"Using fallback bubble point: {pb:.2f} psia due to calculation error")

    try:
        pressures = generate_pressure_range(data, pb)
    except Exception as e:
        logger.error(f"Failed to generate pressure range: {str(e)}")
        step = data.step_size or 25
        pressures = np.arange(0, 5000 + step, step)

    results = []
    calculation_errors = []

    for P in pressures:
        try:
            temp_data = data.copy(update={"pressure": float(P)})
            z = calculate_z(temp_data, method=corr["z"])
            bg = calculate_bg(temp_data, z)
            rs = calculate_rs(temp_data, pressure=P, pb=pb, method=corr["rs"])
            if P >= pb:
                rs = min(rs, data.gor)
            bo = calculate_bo(temp_data, rs=rs, pb=pb, method=corr["bo"])
            mu_o = calculate_mu_o(temp_data, rs=rs, pb=pb, method=corr["mu"])
            co = calculate_co(temp_data, rs=rs, pb=pb, method=corr["co"])
            rho_o = calculate_rho_o(temp_data, rs=rs, bo=bo, method=corr["rho"])
            bt = bo if P <= pb else bo + (data.gor - rs) * bg
            ift = data.ift or calculate_ift(temp_data, rho_o, method=corr["ift"])

            results.append(PVTResult(
                pressure=float(P), z=z, bg=bg, pb=pb, rs=rs, bo=bo,
                mu_o=mu_o, co=co, bt=bt, rho_o=rho_o, ift=ift
            ))
        except Exception as e:
            logger.error(f"Error calculating PVT at {P} psia: {str(e)}")
            calculation_errors.append(f"Failed at P={P} psia: {str(e)}")

    metadata = {
        "correlations_used": corr,
        "bubble_point": pb,
        "warnings": validation["warnings"] + (calculation_errors if calculation_errors else [])
    }

    return {"status": "success", "metadata": metadata, "results": results}

def get_pvt_at_pressure(data: PVTInput, target_pressure: float) -> Optional[PVTResult]:
    temp_data = data.copy(update={"pressure": target_pressure})
    corr = data.correlations or {}
    for prop in ["pb", "rs", "bo", "mu", "co", "rho", "z", "ift"]:
        if prop not in corr:
            corr[prop] = recommend_correlation(data, prop)

    try:
        pb = data.pb or calculate_pb(data, method=corr["pb"])
        z = calculate_z(temp_data, method=corr["z"])
        bg = calculate_bg(temp_data, z)
        rs = calculate_rs(temp_data, pressure=target_pressure, pb=pb, method=corr["rs"])
        if target_pressure >= pb:
            rs = min(rs, data.gor)
        bo = calculate_bo(temp_data, rs=rs, pb=pb, method=corr["bo"])
        mu_o = calculate_mu_o(temp_data, rs=rs, pb=pb, method=corr["mu"])
        co = calculate_co(temp_data, rs=rs, pb=pb, method=corr["co"])
        rho_o = calculate_rho_o(temp_data, rs=rs, bo=bo, method=corr["rho"])
        bt = bo if target_pressure <= pb else bo + (data.gor - rs) * bg
        ift = data.ift or calculate_ift(temp_data, rho_o, method=corr["ift"])

        return PVTResult(
            pressure=target_pressure, z=z, bg=bg, pb=pb, rs=rs,
            bo=bo, mu_o=mu_o, co=co, bt=bt, rho_o=rho_o, ift=ift
        )
    except Exception as e:
        logger.error(f"Failed to calculate PVT at {target_pressure} psia: {str(e)}")
        return None

def bulk_calculate_pvt(data: PVTInput, pressures: List[float]) -> Dict[str, Any]:
    results = []
    errors = []

    for pressure in pressures:
        result = get_pvt_at_pressure(data, pressure)
        if result:
            results.append(result)
        else:
            errors.append(f"Failed calculation at {pressure} psia")

    return {
        "status": "success" if results else "error",
        "messages": errors if errors else [],
        "results": results
    }