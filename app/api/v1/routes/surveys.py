from fastapi import APIRouter, Depends
from app.db.session import session
from app.models.survey import Survey
from app.crud.surveys import get_survey as get_survey_crud
from sqlmodel import Session
router = APIRouter()

@router.get("/{well_id}")
async def get_survey(well_id: str, db: Session = Depends(session)):
    return get_survey_crud(well_id, db)