# backend/pvt/ift.py

def calculate_ift(data, rho_o, method="asheim"):
    rs = getattr(data, "gor", 0)
    co2_frac = getattr(data, "co2_frac", 0.0)

    # Safety fallback
    if rs is None or rho_o is None:
        return None

    # === Method: Asheim (1989) ===
    if method == "asheim":
        # Empirical: more gas → lower IFT
        return max(5.0, 30.0 - 0.1 * rs)

    # === Method: Parachor (Simplified) ===
    elif method == "parachor":
        # Not compositional here, simplified trend
        return max(5.0, 25.0 - 0.05 * rs)

    # === Method: CO2 Adjusted ===
    elif method == "co2_adjusted":
        base = 30.0 - 0.1 * rs
        adjustment = 10.0 * co2_frac
        return max(2.0, base - adjustment)

    # === Default fallback ===
    return max(5.0, 30.0 - 0.1 * rs)