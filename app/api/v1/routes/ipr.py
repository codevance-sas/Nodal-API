# app/api/v1/routes/ipr.py
from fastapi import APIRouter, HTTPException
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Import models
from app.schemas.ipr import IPRInput
from app.services.ipr.engine import calculate_ipr_curve, get_example_input

# Initialize router
router = APIRouter()

@router.post("/calculate")
async def calculate_ipr_endpoint(data: IPRInput):
    """
    Calculate the Inflow Performance Relationship (IPR) curve
    """
    try:
        logger.info(f"Calculating IPR with BOPD={data.BOPD}, BWPD={data.BWPD}, Pr={data.Pr}")
        
        # Call the service function
        result = calculate_ipr_curve(data)
        
        logger.info(f"IPR calculation completed: {len(result['ipr_curve'])} points generated")
        return result
        
    except Exception as e:
        logger.error(f"Error in IPR calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"IPR calculation failed: {str(e)}")
        
@router.get("/example")
async def get_example_ipr_input():
    """
    Get example IPR input parameters
    """
    return get_example_input()