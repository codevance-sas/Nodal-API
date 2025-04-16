# Nodal-API: Petroleum Engineering Calculations API

A FastAPI-based application for performing complex petroleum engineering calculations for oil and gas wells, including PVT analysis and wellbore hydraulics.

## Overview

Nodal-API provides a comprehensive set of endpoints for petroleum engineers to perform critical calculations related to fluid properties and wellbore hydraulics. This API encapsulates industry-standard correlations and methods used in nodal analysis for oil and gas wells.

## Features

### PVT Analysis

The API provides extensive PVT (Pressure-Volume-Temperature) analysis capabilities:

- **Bubble Point Pressure**: Calculate bubble point using multiple correlations (Standing, Vazquez-Beggs, Glaso, Marhoun, Petrosky)
- **Solution Gas-Oil Ratio (Rs)**: Calculate across pressure ranges with various methods
- **Oil Formation Volume Factor (Bo)**: Determine oil volume changes with pressure
- **Oil Viscosity (μo)**: Calculate using Beggs-Robinson or Bergman-Sutton correlations
- **Oil Compressibility (co)**: Determine using Vazquez-Beggs or Standing methods
- **Gas Properties**: Calculate Z-factor, gas formation volume factor, and gas density
- **Interfacial Tension**: Calculate using Asheim, Parachor, or CO2-adjusted methods
- **Correlation Comparison**: Compare different correlation methods for each property

### Wellbore Hydraulics

Comprehensive wellbore flow calculations include:

- **Pressure Traverses**: Calculate pressure profiles along the wellbore
- **Multiphase Flow Patterns**: Determine flow regimes at different depths
- **Pressure Drop Components**: Analyze elevation, friction, and acceleration components
- **Multiple Correlations**: Support for Hagedorn-Brown, Beggs-Brill, Duns-Ross, and other industry-standard methods

## API Endpoints

### PVT Endpoints

- `POST /api/pvt/curve`: Generate comprehensive PVT property curves
- `POST /api/pvt/curve/recommended`: Get PVT curves using recommended correlations
- `POST /api/pvt/curve/compare/{property_name}`: Compare different correlations for specific properties
- `POST /api/pvt/curve/bubble-points`: Calculate bubble points using different methods

### Hydraulics Endpoints

- `POST /hydraulics/calculate`: Calculate pressure profile and hydraulics parameters
- `GET /hydraulics/methods`: List available correlation methods
- `GET /hydraulics/example-input`: Get example input for hydraulics calculations

## Using the API

### PVT Analysis Example

```python
import requests
import json

# API endpoint
url = "http://localhost:8000/api/pvt/curve"

# Sample input data
data = {
    "api": 35.0,
    "gas_gravity": 0.65,
    "gor": 800,
    "temperature": 180.0,
    "co2_frac": 0.02,
    "h2s_frac": 0.0,
    "n2_frac": 0.01
}

# Make the request
response = requests.post(url, json=data)
results = response.json()

# Access the results
bubble_points = results["metadata"]["bubble_points"]
pressure_array = results["pressure"]
bo_values = results["bo"]["standing"]

print(f"Standing Bubble Point: {bubble_points['standing']} psia")
```

### Wellbore Hydraulics Example

```python
import requests
import json

# API endpoint
url = "http://localhost:8000/hydraulics/calculate"

# Sample input data
data = {
    "fluid_properties": {
        "oil_rate": 500.0,
        "water_rate": 100.0,
        "gas_rate": 1000.0,
        "oil_gravity": 35.0,
        "water_gravity": 1.05,
        "gas_gravity": 0.65,
        "bubble_point": 2500.0,
        "temperature_gradient": 0.015,
        "surface_temperature": 75.0
    },
    "wellbore_geometry": {
        "depth": 10000.0,
        "deviation": 0.0,
        "tubing_id": 2.441,
        "roughness": 0.0006,
        "depth_steps": 100
    },
    "method": "hagedorn-brown",
    "surface_pressure": 100.0,
    "bhp_mode": "calculate"
}

# Make the request
response = requests.post(url, json=data)
results = response.json()

# Access the results
bhp = results["bottomhole_pressure"]
pressure_profile = results["pressure_profile"]
elevation_drop_pct = results["elevation_drop_percentage"]
friction_drop_pct = results["friction_drop_percentage"]

print(f"Bottomhole Pressure: {bhp} psia")
print(f"Elevation Pressure Drop: {elevation_drop_pct}%")
print(f"Friction Pressure Drop: {friction_drop_pct}%")
```

## Technical Notes

### PVT Correlation Applicability

Different PVT correlations have varying ranges of applicability based on fluid properties:

- **Standing**: Best for moderate API gravities (20-45°API) and GORs (150-1500 scf/STB)
- **Vazquez-Beggs**: Covers wider range of API gravities, with separate equations for below and above 30°API
- **Glaso**: Good for North Sea crude oil systems
- **Marhoun**: Developed for Middle East crude oils
- **Petrosky**: Best for Gulf of Mexico oils with high reservoir temperatures

### Hydraulics Correlation Selection

Guidelines for selecting the appropriate hydraulics correlation:

- **Hagedorn-Brown**: Good for vertical wells with varying flow rates
- **Beggs-Brill**: Best for deviated or horizontal wells
- **Duns-Ross**: Effective for vertical gas-dominant flow
- **Orkiszewski**: Good for slug flow regimes in vertical wells
- **Mukherjee-Brill**: Enhanced for high-angle and horizontal wells

## Installation and Deployment

### Prerequisites
- Python 3.10+
- FastAPI
- Numpy

### Running Locally
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker Deployment
```bash
docker build -t nodal-api .
docker run -p 8000:8000 nodal-api
```

## License

Copyright (c) 2023
