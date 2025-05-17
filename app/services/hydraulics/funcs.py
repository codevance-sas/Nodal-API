def available_methods():
    return [
            {
                "id": "hagedorn-brown",
                "name": "Hagedorn-Brown",
                "description": "Vertical multiphase flow correlation for oil and gas wells"
            },
            {
                "id": "beggs-brill",
                "name": "Beggs-Brill",
                "description": "Inclined multiphase flow correlation for all inclination angles"
            },
            {
                "id": "duns-ross",
                "name": "Duns-Ross",
                "description": "Vertical flow correlation based on flow pattern transitions"
            },
            {
                "id": "chokshi",
                "name": "Chokshi",
                "description": "Modern mechanistic model for multiphase flow in wellbores"
            },
            {
                "id": "orkiszewski",
                "name": "Orkiszewski",
                "description": "Specialized correlation for wells with large tubing diameters"
            },
            {
                "id": "gray",
                "name": "Gray",
                "description": "Correlation developed for high-rate gas wells and high Reynolds numbers"
            },
            {
                "id": "mukherjee-brill",
                "name": "Mukherjee-Brill",
                "description": "Specialized correlation for directional and deviated wells"
            },
            {
                "id": "aziz",
                "name": "Aziz et al.",
                "description": "Correlation for wide range of gas-liquid ratios with flow pattern transitions"
            },
            {
                "id": "hasan-kabir",
                "name": "Hasan-Kabir",
                "description": "Correlation considering pipe roughness effects on pressure drop calculations"
            },
            {
                "id": "ansari",
                "name": "Ansari",
                "description": "Mechanistic model for flow pattern prediction and pressure gradient calculations"
            }
        ]

def available_gas_correlations():
    return [
            {
                "id": "weymouth",
                "name": "Weymouth",
                "description": "For high-pressure gas transmission pipelines with turbulent flow"
            },
            {
                "id": "panhandle_a",
                "name": "Panhandle A",
                "description": "For long-distance gas transmission pipelines with partial turbulence"
            },
            {
                "id": "panhandle_b",
                "name": "Panhandle B",
                "description": "Modern update of Panhandle A for high-pressure gas transmission"
            }
        ]

def recommend_gas_correlation(gas_rate, pipe_diameter, pipe_length, pressure):
    """
    Recommend the most appropriate gas flow correlation based on input parameters.
    
    Args:
        gas_rate: Gas flow rate in Mscf/d
        pipe_diameter: Pipe diameter in inches
        pipe_length: Pipe length in feet
        pressure: Average pressure in psia
        
    Returns:
        Recommended correlation ID
    """
    # Calculate velocity-based Reynolds number indicator
    # This is a simplified approach - full calculation would need density and viscosity
    velocity_indicator = gas_rate / (pipe_diameter ** 2)
    
    # Calculate pressure-length indicator
    pressure_length_indicator = pressure / pipe_length
    
    # Decision logic
    if pipe_diameter >= 20:
        # Very large diameter pipes typically use Panhandle B
        return "panhandle_b"
    elif pipe_length > 50000:  # > ~10 miles
        # Long-distance transmission typically uses Panhandle
        if velocity_indicator > 50:
            # High-velocity long distance - use newer Panhandle B
            return "panhandle_b"
        else:
            # Moderate velocity long distance - use Panhandle A
            return "panhandle_a"
    else:
        # Shorter pipes or gathering systems - use Weymouth
        return "weymouth"

def get_standard_pipe_sizes():
    """
    Return standard pipe sizes in inches.
    """
    return [
        0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 
        8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 
        36.0, 42.0, 48.0, 56.0, 60.0
    ]