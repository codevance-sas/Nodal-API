import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session

logger = logging.getLogger("surveys")
router = APIRouter(prefix="/directional_surveys", tags=["directional_surveys"])


@router.get("/operators", response_model=List[str])
def get_all_operators(db: Session = Depends(get_session)):
    """
    SELECT DISTINCT operator_name
      FROM directional_surveys
     WHERE operator_name IS NOT NULL
       AND trim(operator_name) <> ''
     ORDER BY operator_name;
    """
    try:
        sql = text(
            "SELECT DISTINCT operator_name "
            "FROM directional_surveys "
            "WHERE operator_name IS NOT NULL "
            "  AND trim(operator_name) != '' "
            "ORDER BY operator_name;"
        )
        rows = db.exec(sql).all()
        names = [r[0] for r in rows if r[0]]
        logger.info(f"[operators] {len(names)} entries; sample: {names[:5]}")
        return names

    except Exception as e:
        logger.exception("Operators query failed")
        raise HTTPException(500, f"Operators query failed: {e}")


@router.get("/wells", response_model=List[str])
def get_wells_by_operator(
    operator: str = Query(..., description="Operator name"),
    db: Session = Depends(get_session),
):
    """
    SELECT DISTINCT well_name
      FROM directional_surveys
     WHERE operator_name = :operator
       AND well_name IS NOT NULL
       AND trim(well_name) <> ''
     ORDER BY well_name;
    """
    try:
        sql = text(
            "SELECT DISTINCT well_name "
            "FROM directional_surveys "
            "WHERE operator_name = :operator "
            "  AND well_name IS NOT NULL "
            "  AND trim(well_name) != '' "
            "ORDER BY well_name;"
        ).bindparams(operator=operator)

        logger.info(f"[wells] operator={operator!r}")
        rows = db.exec(sql).all()
        wells = [r[0] for r in rows if r[0]]
        logger.info(f"[wells] {len(wells)} entries; sample: {wells[:5]}")
        return wells

    except Exception as e:
        logger.exception(f"Wells query failed for {operator!r}")
        raise HTTPException(500, f"Wells query failed for {operator!r}: {e}")


@router.get("/surveys", response_model=List[dict])
def get_surveys_for_well(
    well: str = Query(..., description="Well name"),
    db: Session = Depends(get_session),
):
    """
    SELECT * FROM directional_surveys
     WHERE well_name = :well
    """
    try:
        sql = text(
            "SELECT * "
            "FROM directional_surveys "
            "WHERE well_name = :well "
            "ORDER BY md;"
        ).bindparams(well=well)

        rows = db.exec(sql).all()
        # each row is a Row object; convert to dict
        data = [dict(r._mapping) for r in rows]
        logger.info(f"[surveys] {len(data)} points for well={well!r}")
        return data

    except Exception as e:
        logger.exception(f"Surveys query failed for {well!r}")
        raise HTTPException(500, f"Surveys query failed for {well!r}: {e}")
