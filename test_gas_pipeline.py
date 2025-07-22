"""
Test script for the refactored gas pipeline correlation methods.
This script tests the Panhandle and Weymouth methods to verify that they work correctly.
"""

import sys
import os
from pprint import pprint

# Add the project root to the Python path
sys.path.append(os.path.abspath('.'))

# Import the original functions
from app.services.hydraulics.correlations.panhandle import (
    calculate_panhandle_a as original_panhandle_a,
    calculate_panhandle_b as original_panhandle_b,
    calculate_max_flow_rate_panhandle as original_max_flow_panhandle,
    calculate_diameter_panhandle as original_diameter_panhandle
)
from app.services.hydraulics.correlations.weymouth import (
    calculate_weymouth as original_weymouth,
    calculate_max_flow_rate as original_max_flow_weymouth,
    calculate_diameter_weymouth as original_diameter_weymouth
)

# Import the refactored functions
from app.services.hydraulics.correlations.panhandle_refactored import (
    calculate_panhandle_a as refactored_panhandle_a,
    calculate_panhandle_b as refactored_panhandle_b,
    calculate_max_flow_rate_panhandle as refactored_max_flow_panhandle,
    calculate_diameter_panhandle as refactored_diameter_panhandle
)
from app.services.hydraulics.correlations.weymouth_refactored import (
    calculate_weymouth as refactored_weymouth,
    calculate_max_flow_rate as refactored_max_flow_weymouth,
    calculate_diameter_weymouth as refactored_diameter_weymouth
)

def compare_results(original_result, refactored_result, name):
    """Compare the results of the original and refactored functions."""
    print(f"\nComparing {name} results:")
    
    if isinstance(original_result, dict) and isinstance(refactored_result, dict):
        # Compare dictionaries
        all_keys = set(original_result.keys()) | set(refactored_result.keys())
        for key in all_keys:
            if key in original_result and key in refactored_result:
                original_value = original_result[key]
                refactored_value = refactored_result[key]
                
                if isinstance(original_value, (int, float)) and isinstance(refactored_value, (int, float)):
                    # Compare numeric values with tolerance
                    diff = abs(original_value - refactored_value)
                    rel_diff = diff / max(abs(original_value), 1e-10)
                    if rel_diff > 1e-6:
                        print(f"  {key}: Original={original_value}, Refactored={refactored_value}, Relative diff={rel_diff}")
                    else:
                        print(f"  {key}: Match (within tolerance)")
                else:
                    # Compare non-numeric values
                    if original_value != refactored_value:
                        print(f"  {key}: Original={original_value}, Refactored={refactored_value}")
                    else:
                        print(f"  {key}: Match")
            else:
                # Key exists in only one result
                if key in original_result:
                    print(f"  {key}: Only in original result: {original_result[key]}")
                else:
                    print(f"  {key}: Only in refactored result: {refactored_result[key]}")
    else:
        # Compare non-dictionary values
        diff = abs(original_result - refactored_result)
        rel_diff = diff / max(abs(original_result), 1e-10)
        if rel_diff > 1e-6:
            print(f"  Original={original_result}, Refactored={refactored_result}, Relative diff={rel_diff}")
        else:
            print(f"  Match (within tolerance)")

def test_panhandle_a():
    """Test the Panhandle A method."""
    print("\nTesting Panhandle A method...")
    
    # Test parameters
    diameter = 12.0  # inches
    length = 10000.0  # feet
    gas_rate = 10000.0  # Mscf/d
    inlet_pressure = 1000.0  # psia
    gas_gravity = 0.65
    temperature = 80.0  # °F
    
    # Calculate using original and refactored functions
    original_result = original_panhandle_a(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_panhandle_a(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    # Compare results
    compare_results(original_result, refactored_result, "Panhandle A")

def test_panhandle_b():
    """Test the Panhandle B method."""
    print("\nTesting Panhandle B method...")
    
    # Test parameters
    diameter = 12.0  # inches
    length = 10000.0  # feet
    gas_rate = 10000.0  # Mscf/d
    inlet_pressure = 1000.0  # psia
    gas_gravity = 0.65
    temperature = 80.0  # °F
    
    # Calculate using original and refactored functions
    original_result = original_panhandle_b(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_panhandle_b(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    # Compare results
    compare_results(original_result, refactored_result, "Panhandle B")

def test_weymouth():
    """Test the Weymouth method."""
    print("\nTesting Weymouth method...")
    
    # Test parameters
    diameter = 12.0  # inches
    length = 10000.0  # feet
    gas_rate = 10000.0  # Mscf/d
    inlet_pressure = 1000.0  # psia
    gas_gravity = 0.65
    temperature = 80.0  # °F
    
    # Calculate using original and refactored functions
    original_result = original_weymouth(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_weymouth(
        diameter=diameter,
        length=length,
        gas_rate=gas_rate,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    # Compare results
    compare_results(original_result, refactored_result, "Weymouth")

def test_max_flow_rate():
    """Test the maximum flow rate calculations."""
    print("\nTesting maximum flow rate calculations...")
    
    # Test parameters
    diameter = 12.0  # inches
    length = 10000.0  # feet
    inlet_pressure = 1000.0  # psia
    gas_gravity = 0.65
    temperature = 80.0  # °F
    
    # Test Panhandle A
    original_result = original_max_flow_panhandle(
        equation="a",
        diameter=diameter,
        length=length,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_max_flow_panhandle(
        equation="a",
        diameter=diameter,
        length=length,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    compare_results(original_result, refactored_result, "Max flow rate (Panhandle A)")
    
    # Test Panhandle B
    original_result = original_max_flow_panhandle(
        equation="b",
        diameter=diameter,
        length=length,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_max_flow_panhandle(
        equation="b",
        diameter=diameter,
        length=length,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    compare_results(original_result, refactored_result, "Max flow rate (Panhandle B)")
    
    # Test Weymouth
    original_result = original_max_flow_weymouth(
        diameter=diameter,
        length=length,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_max_flow_weymouth(
        diameter=diameter,
        length=length,
        inlet_pressure=inlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    compare_results(original_result, refactored_result, "Max flow rate (Weymouth)")

def test_diameter_calculation():
    """Test the diameter calculations."""
    print("\nTesting diameter calculations...")
    
    # Test parameters
    gas_rate = 10000.0  # Mscf/d
    length = 10000.0  # feet
    inlet_pressure = 1000.0  # psia
    outlet_pressure = 800.0  # psia
    gas_gravity = 0.65
    temperature = 80.0  # °F
    
    # Test Panhandle A
    original_result = original_diameter_panhandle(
        equation="a",
        gas_rate=gas_rate,
        length=length,
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_diameter_panhandle(
        equation="a",
        gas_rate=gas_rate,
        length=length,
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    compare_results(original_result, refactored_result, "Diameter (Panhandle A)")
    
    # Test Panhandle B
    original_result = original_diameter_panhandle(
        equation="b",
        gas_rate=gas_rate,
        length=length,
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_diameter_panhandle(
        equation="b",
        gas_rate=gas_rate,
        length=length,
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    compare_results(original_result, refactored_result, "Diameter (Panhandle B)")
    
    # Test Weymouth
    original_result = original_diameter_weymouth(
        gas_rate=gas_rate,
        length=length,
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    refactored_result = refactored_diameter_weymouth(
        gas_rate=gas_rate,
        length=length,
        inlet_pressure=inlet_pressure,
        outlet_pressure=outlet_pressure,
        gas_gravity=gas_gravity,
        temperature=temperature
    )
    
    compare_results(original_result, refactored_result, "Diameter (Weymouth)")

if __name__ == "__main__":
    print("Testing gas pipeline correlation methods...")
    test_panhandle_a()
    test_panhandle_b()
    test_weymouth()
    test_max_flow_rate()
    test_diameter_calculation()
    print("\nAll tests completed.")