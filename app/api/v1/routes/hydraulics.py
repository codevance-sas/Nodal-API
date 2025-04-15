# backend/hydraulics/api.py
from fastapi import APIRouter, HTTPException
from app.schemas.hydraulics import HydraulicsInput, HydraulicsResult
from app.services.hydraulics.engine import calculate_hydraulics
from app.services.hydraulics.funcs import available_methods
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    tags=["hydraulics"],
    responses={404: {"description": "Not found"}},
)

@router.post("/calculate")
async def calculate_hydraulics_endpoint(data: HydraulicsInput) -> HydraulicsResult:
    """
    Calculate pressure profile and hydraulics parameters using the selected correlation
    """
    try:
        logger.info(f"Received hydraulics calculation request using {data.method} method")
        result = calculate_hydraulics(data)
        logger.info(f"Calculation completed: BHP={result.bottomhole_pressure:.2f} psia")
        return result
    except Exception as e:
        logger.error(f"Error in hydraulics calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/methods")
async def get_available_methods():
    """
    Return the list of available correlation methods
    """
    return {
        "methods": available_methods()
    }

@router.get("/example-input")
async def get_example_input():
    """
    Return an example input for the hydraulics calculation
    """
    return HydraulicsInput(
        fluid_properties={
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
        wellbore_geometry={
            "depth": 10000.0,
            "deviation": 0.0,
            "tubing_id": 2.441,
            "roughness": 0.0006,
            "depth_steps": 100
        },
        method="hagedorn-brown",
        surface_pressure=100.0,
        bhp_mode="calculate"
    )