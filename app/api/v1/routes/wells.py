from fastapi import APIRouter, Depends
from app.db.session import session
from app.models.survey import Well  
from app.crud.wells import get_all_wells, get_well as get_well_crud
from sqlmodel import Session
router = APIRouter()

@router.get("/")
async def get_wells(db: Session = Depends(session)):
    return get_all_wells(db)

@router.get("/{well_id}")
async def get_well(well_id: int, db: Session = Depends(session)):
    return get_well_crud(well_id, db)


