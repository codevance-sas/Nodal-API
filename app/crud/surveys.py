from app.models.survey import Survey
from sqlmodel import Session, select, func

def get_survey(well_id: str, session: Session) -> Survey | None:
    return session.exec(
        select(
            Survey,
            (Survey.md - func.lag(Survey.md).over(partition_by=Survey.well_id, order_by=Survey.survey)).label('md_diff')
        )
        .where(Survey.well_id == well_id)
        .order_by(Survey.survey.asc())
    ).all()