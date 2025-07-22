"""
Test script for the refactored hydraulics correlation methods.
This script creates a sample HydraulicsInput object with pipe segments and survey data,
then calls the hydraulics engine for each correlation method to verify that they work correctly.
"""

import sys
import os
from pprint import pprint

# Add the project root to the Python path
sys.path.append(os.path.abspath('.'))

from app.schemas.hydraulics import (
    HydraulicsInput, 
    FluidPropertiesInput, 
    WellboreGeometryInput,
    PipeSegment,
    SurveyData
)
from app.services.hydraulics.engine import calculate_hydraulics_method

def create_test_input():
    """Create a sample HydraulicsInput object with pipe segments and survey data."""
    # Create fluid properties
    fluid = FluidPropertiesInput(
        oil_rate=1000.0,
        water_rate=500.0,
        gas_rate=2000.0,
        oil_gravity=35.0,
        gas_gravity=0.65,
        bubble_point=2000.0,
        temperature_gradient=0.01,
        surface_temperature=80.0
    )
    
    # Create pipe segments
    pipe_segments = [
        PipeSegment(start_depth=0.0, end_depth=5000.0, diameter=3.5),
        PipeSegment(start_depth=5000.0, end_depth=10000.0, diameter=2.875)
    ]
    
    # Create wellbore geometry
    wellbore = WellboreGeometryInput(
        pipe_segments=pipe_segments,
        deviation=15.0,  # Default deviation if no survey data
        roughness=0.0006,
        depth_steps=100
    )
    
    # Create survey data
    survey_data = [
        SurveyData(md=0.0, tvd=0.0, inclination=0.0),
        SurveyData(md=2500.0, tvd=2450.0, inclination=10.0),
        SurveyData(md=5000.0, tvd=4800.0, inclination=15.0),
        SurveyData(md=7500.0, tvd=7000.0, inclination=20.0),
        SurveyData(md=10000.0, tvd=9100.0, inclination=25.0)
    ]
    
    # Create hydraulics input
    return HydraulicsInput(
        fluid_properties=fluid,
        wellbore_geometry=wellbore,
        method="hagedorn-brown",  # Default method, will be overridden
        surface_pressure=500.0,
        survey_data=survey_data
    )

def test_all_methods():
    """Test all hydraulics correlation methods."""
    # List of all methods to test
    methods = [
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
    
    # Create test input
    base_input = create_test_input()
    
    # Test each method
    results = {}
    for method in methods:
        print(f"\nTesting method: {method}")
        try:
            # Create a copy of the input with the current method
            input_data = HydraulicsInput(
                fluid_properties=base_input.fluid_properties,
                wellbore_geometry=base_input.wellbore_geometry,
                method=method,
                surface_pressure=base_input.surface_pressure,
                survey_data=base_input.survey_data
            )
            
            # Calculate hydraulics
            result = calculate_hydraulics_method(input_data)
            
            # Store and print results
            results[method] = {
                "bottomhole_pressure": result.bottomhole_pressure,
                "overall_pressure_drop": result.overall_pressure_drop,
                "elevation_drop_percentage": result.elevation_drop_percentage,
                "friction_drop_percentage": result.friction_drop_percentage,
                "acceleration_drop_percentage": result.acceleration_drop_percentage
            }
            
            print(f"  Bottomhole pressure: {result.bottomhole_pressure:.2f} psia")
            print(f"  Overall pressure drop: {result.overall_pressure_drop:.2f} psi")
            print(f"  Elevation: {result.elevation_drop_percentage:.2f}%")
            print(f"  Friction: {result.friction_drop_percentage:.2f}%")
            print(f"  Acceleration: {result.acceleration_drop_percentage:.2f}%")
            
            # Check if the result is reasonable
            if result.bottomhole_pressure < base_input.surface_pressure:
                print("  WARNING: Bottomhole pressure is less than surface pressure!")
            if result.bottomhole_pressure > 10000:
                print("  WARNING: Bottomhole pressure seems too high!")
            if result.elevation_drop_percentage < 0 or result.elevation_drop_percentage > 100:
                print("  WARNING: Elevation drop percentage is out of range!")
            if result.friction_drop_percentage < 0 or result.friction_drop_percentage > 100:
                print("  WARNING: Friction drop percentage is out of range!")
                
            print("  SUCCESS: Method completed without errors")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            results[method] = {"error": str(e)}
    
    # Print summary
    print("\nSummary of results:")
    print("==================")
    for method, result in results.items():
        if "error" in result:
            print(f"{method}: ERROR - {result['error']}")
        else:
            print(f"{method}: BHP = {result['bottomhole_pressure']:.2f} psia")
    
    # Check if all methods worked
    all_success = all("error" not in result for result in results.values())
    if all_success:
        print("\nAll methods completed successfully!")
    else:
        print("\nSome methods failed. See errors above.")
    
    return results

if __name__ == "__main__":
    test_all_methods()