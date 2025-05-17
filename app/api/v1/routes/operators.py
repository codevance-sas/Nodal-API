from fastapi import APIRouter, Depends
from app.db.session import session
from app.models.survey import Operator
from app.crud.operators import get_all_operators, create_operator as create_operator_crud, update_operator as update_operator_crud, delete_operator as delete_operator_crud, get_operator as get_operator_crud
from sqlmodel import Session
router = APIRouter(tags=["directional_surveys"])

@router.get("/")
async def get_operators(db: Session = Depends(session)):
    return get_all_operators(db)

@router.post("/")
async def create_operator(operator: Operator, db: Session = Depends(session)):
    return create_operator_crud(operator, db)

@router.put("/{operator_id}")
async def update_operator(operator_id: int, operator: Operator, db: Session = Depends(session)):
    return update_operator_crud(operator_id, operator, db)

@router.delete("/{operator_id}")
async def delete_operator(operator_id: int, db: Session = Depends(session)):
    return delete_operator_crud(operator_id, dbd)

@router.get("/{operator_id}")
async def get_operator(operator_id: int, db: Session = Depends(session)):
    return get_operator_crud(operator_id, db)