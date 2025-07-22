import logging
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Any, Optional

from app.schemas.hydraulics import (
    HydraulicsInput, HydraulicsResult,
    FlowRateInput, GeometryInput
)
from app.services.hydraulics import hydraulics_service

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["hydraulics"])


@router.post(
    "/calculate",
    response_model=HydraulicsResult,
    summary="Calculate well hydraulics",
)
async def calculate_hydraulics_endpoint(
    data: HydraulicsInput,
) -> HydraulicsResult:
    """
    Calculate pressure profile and hydraulics parameters using the selected correlation.
    
    This endpoint performs hydraulic calculations for a wellbore using the specified correlation method.
    It calculates the pressure profile from surface to bottomhole, accounting for fluid properties,
    wellbore geometry, and survey data if provided.
    
    Available correlation methods include:
    - hagedorn-brown: Suitable for vertical and deviated wells with various flow patterns
    - beggs-brill: Suitable for horizontal, inclined, and vertical pipes
    - duns-ross: Suitable for vertical flow with various flow patterns
    - chokshi: Modified Hagedorn-Brown for high-rate gas wells
    - orkiszewski: Suitable for vertical flow with accurate flow pattern prediction
    - gray: Suitable for high-pressure gas wells
    - mukherjee-brill: Suitable for directional wells
    - aziz: Suitable for vertical and slightly deviated wells
    - hasan-kabir: Suitable for vertical and deviated wells with accurate flow pattern prediction
    - ansari: Suitable for vertical flow with mechanistic modeling
    
    Parameters:
    - data: Input data containing fluid properties, wellbore geometry, and calculation parameters
    
    Returns:
    - Pressure profile along the wellbore
    - Bottomhole pressure
    - Flow pattern distribution
    - Pressure drop components (elevation, friction, acceleration)
    - Other hydraulic parameters (holdups, velocities, etc.)
    
    Example:
    ```json
    {
      "fluid_properties": {
        "oil_rate": 1000,
        "water_rate": 500,
        "gas_rate": 2000,
        "oil_gravity": 35,
        "gas_gravity": 0.65,
        "water_gravity": 1.05,
        "bubble_point": 2000,
        "temperature_gradient": 0.01,
        "surface_temperature": 80
      },
      "wellbore_geometry": {
        "pipe_segments": [
          {"start_depth": 0, "end_depth": 5000, "diameter": 3.5},
          {"start_depth": 5000, "end_depth": 10000, "diameter": 2.875}
        ],
        "roughness": 0.0006,
        "depth_steps": 100
      },
      "method": "hagedorn-brown",
      "surface_pressure": 500
    }
    ```
    """
    try:
        return hydraulics_service.calculate_hydraulics(data)
    except Exception as e:
        logger.error(f"Error in hydraulics calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend")
async def recommend_method_endpoint(data: HydraulicsInput) -> Dict[str, str]:
    """
    Recommend the most suitable correlation method based on input data.
    
    This endpoint analyzes the provided wellbore and fluid properties to recommend
    the most appropriate correlation method for hydraulic calculations. The recommendation
    is based on factors such as:
    - Well deviation (vertical, deviated, horizontal)
    - Flow rates and fluid properties
    - Expected flow patterns
    - Pressure and temperature conditions
    
    Parameters:
    - data: Input data containing fluid properties and wellbore geometry
    
    Returns:
    - A dictionary with a single key "recommended_method" containing the name of the
      recommended correlation method
    
    Example response:
    ```json
    {
      "recommended_method": "hagedorn-brown"
    }
    ```
    
    Note: The same input format as the /calculate endpoint is used, but the "method"
    field is ignored since the purpose is to determine the appropriate method.
    """
    try:
        method = hydraulics_service.recommend_method(data)
        return {"recommended_method": method}
    except Exception as e:
        logger.error(f"Error in method recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_methods_endpoint(
    data: HydraulicsInput,
    methods: Optional[List[str]] = Query(None, description="List of methods to compare")
) -> Dict[str, Any]:
    """
    Compare results from different hydraulics correlations.
    
    This endpoint calculates hydraulic parameters using multiple correlation methods
    and returns the results for comparison. This is useful for:
    - Evaluating which correlation method is most appropriate for a specific well
    - Understanding the range of possible results from different methods
    - Validating results by comparing multiple methods
    
    Parameters:
    - data: Input data containing fluid properties and wellbore geometry
    - methods: Optional list of correlation methods to compare. If not provided,
      all available methods will be used. Specify as query parameters, e.g.,
      ?methods=hagedorn-brown&methods=beggs-brill
    
    Returns:
    - A dictionary with results from each correlation method, including:
      - Bottomhole pressure
      - Pressure profile
      - Flow patterns
      - Pressure drop components
    - Summary statistics comparing the methods
    
    Example response:
    ```json
    {
      "summary": {
        "min_bhp": 3245.6,
        "max_bhp": 3567.8,
        "avg_bhp": 3412.5,
        "std_dev": 98.7
      },
      "results": {
        "hagedorn-brown": {
          "bottomhole_pressure": 3456.7,
          "overall_pressure_drop": 2956.7,
          "elevation_drop_percentage": 85.2,
          "friction_drop_percentage": 14.8
        },
        "beggs-brill": {
          "bottomhole_pressure": 3378.2,
          "overall_pressure_drop": 2878.2,
          "elevation_drop_percentage": 82.1,
          "friction_drop_percentage": 17.9
        },
        ...
      }
    }
    ```
    """
    try:
        return hydraulics_service.compare_methods(data, methods)
    except Exception as e:
        logger.error(f"Error in method comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/methods")
async def get_available_methods():
    """
    Return the list of available correlation methods.
    
    This endpoint provides a list of all available correlation methods that can be used
    with the hydraulics calculation endpoints. Each method is specialized for certain
    well conditions and fluid properties.
    
    No parameters are required for this endpoint.
    
    Returns:
    - A dictionary with a single key "methods" containing an array of method names
    
    Example response:
    ```json
    {
      "methods": [
        "hagedorn-brown",
        "beggs-brill",
        "duns-ross",
        "chokshi",
        "orkiszewski",
        "gray",
        "mukherjee-brill",
        "aziz",
        "hasan-kabir",
        "ansari"
      ]
    }
    ```
    
    These method names can be used in the "method" field of the input data for the
    /calculate endpoint, or as query parameters for the /compare endpoint.
    """
    return {
        "methods": hydraulics_service.get_available_methods()
    }


@router.post("/sensitivity/flowrate")
async def flow_rate_sensitivity_endpoint(data: FlowRateInput) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on flow rates.
    
    This endpoint calculates how bottomhole pressure and other hydraulic parameters
    change with varying oil flow rates. This is useful for:
    - Production optimization
    - Nodal analysis
    - Understanding the impact of flow rate changes on wellbore performance
    - Determining the maximum flow rate capability of a well
    
    Parameters:
    - data: Input data containing:
      - base_data: Base hydraulics input (same as /calculate endpoint)
      - min_oil_rate: Minimum oil rate for sensitivity analysis (STB/d)
      - max_oil_rate: Maximum oil rate for sensitivity analysis (STB/d)
      - steps: Number of steps between min and max rates
      - water_cut: Water cut as fraction (0-1)
      - gor: Gas-oil ratio (scf/STB)
    
    Returns:
    - A dictionary containing:
      - base_case: Results for the base case
      - sensitivity_results: Array of results for each flow rate step
      - summary: Summary statistics and trends
    
    Example response:
    ```json
    {
      "base_case": {
        "oil_rate": 1000,
        "bottomhole_pressure": 3456.7
      },
      "sensitivity_results": [
        {
          "oil_rate": 500,
          "bottomhole_pressure": 2987.3,
          "elevation_drop_percentage": 82.5,
          "friction_drop_percentage": 17.5
        },
        {
          "oil_rate": 1000,
          "bottomhole_pressure": 3456.7,
          "elevation_drop_percentage": 78.2,
          "friction_drop_percentage": 21.8
        },
        {
          "oil_rate": 1500,
          "bottomhole_pressure": 4123.5,
          "elevation_drop_percentage": 72.1,
          "friction_drop_percentage": 27.9
        }
      ],
      "summary": {
        "optimal_rate": 1200,
        "pressure_trend": "increasing",
        "friction_trend": "increasing"
      }
    }
    ```
    """
    try:
        return hydraulics_service.flow_rate_sensitivity(data)
    except Exception as e:
        logger.error(f"Error in flow rate sensitivity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sensitivity/tubing")
async def tubing_sensitivity_endpoint(data: GeometryInput) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on tubing diameter.
    
    This endpoint calculates how bottomhole pressure and other hydraulic parameters
    change with varying tubing diameters. This is useful for:
    - Tubing size optimization
    - Well design and completion planning
    - Workover and recompletion analysis
    - Understanding the impact of tubing restrictions on well performance
    
    Parameters:
    - data: Input data containing:
      - base_data: Base hydraulics input (same as /calculate endpoint)
      - min_tubing_id: Minimum tubing inner diameter for sensitivity analysis (inches)
      - max_tubing_id: Maximum tubing inner diameter for sensitivity analysis (inches)
      - steps: Number of steps between min and max diameters
    
    Returns:
    - A dictionary containing:
      - base_case: Results for the base case
      - sensitivity_results: Array of results for each tubing diameter
      - summary: Summary statistics and optimal diameter recommendation
    
    Example response:
    ```json
    {
      "base_case": {
        "tubing_id": 2.875,
        "bottomhole_pressure": 3456.7
      },
      "sensitivity_results": [
        {
          "tubing_id": 2.375,
          "bottomhole_pressure": 3789.2,
          "elevation_drop_percentage": 75.3,
          "friction_drop_percentage": 24.7
        },
        {
          "tubing_id": 2.875,
          "bottomhole_pressure": 3456.7,
          "elevation_drop_percentage": 78.2,
          "friction_drop_percentage": 21.8
        },
        {
          "tubing_id": 3.5,
          "bottomhole_pressure": 3234.1,
          "elevation_drop_percentage": 82.5,
          "friction_drop_percentage": 17.5
        }
      ],
      "summary": {
        "optimal_diameter": 3.5,
        "pressure_trend": "decreasing",
        "friction_trend": "decreasing"
      }
    }
    ```
    """
    try:
        return hydraulics_service.tubing_sensitivity(data)
    except Exception as e:
        logger.error(f"Error in tubing sensitivity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/example-input")
async def get_example_input_endpoint():
    """
    Return an example input for the hydraulics calculation.
    
    This endpoint provides a complete example of the input data structure required
    for the /calculate endpoint. This is useful for:
    - Understanding the required input format
    - Testing the API
    - Creating templates for your own calculations
    
    No parameters are required for this endpoint.
    
    Returns:
    - A complete HydraulicsInput object with sample values for all fields
    
    Example response:
    ```json
    {
      "fluid_properties": {
        "oil_rate": 1000,
        "water_rate": 500,
        "gas_rate": 2000,
        "oil_gravity": 35,
        "gas_gravity": 0.65,
        "water_gravity": 1.05,
        "bubble_point": 2000,
        "temperature_gradient": 0.01,
        "surface_temperature": 80
      },
      "wellbore_geometry": {
        "pipe_segments": [
          {"start_depth": 0, "end_depth": 5000, "diameter": 3.5},
          {"start_depth": 5000, "end_depth": 10000, "diameter": 2.875}
        ],
        "roughness": 0.0006,
        "depth_steps": 100
      },
      "method": "hagedorn-brown",
      "surface_pressure": 500,
      "survey_data": [
        {"md": 0, "tvd": 0, "inclination": 0},
        {"md": 5000, "tvd": 4800, "inclination": 15},
        {"md": 10000, "tvd": 9100, "inclination": 25}
      ]
    }
    ```
    
    You can use this example as a starting point and modify the values as needed
    for your specific well conditions.
    """
    return hydraulics_service.get_example_input()