from app.models.survey import Survey
from sqlmodel import Session, select, func
from typing import List
from app.schemas.surveys import SurveyWithDiff


def get_survey(well_id: str, session: Session) -> List[SurveyWithDiff]:
    results = session.exec(
        select(
            Survey,
            func.coalesce(Survey.md - func.lag(Survey.md).over(partition_by=Survey.well_id, order_by=Survey.survey), 0).label('md_diff'),
            func.coalesce(Survey.tvd - func.lag(Survey.tvd).over(partition_by=Survey.well_id, order_by=Survey.survey), 0).label('tvd_diff')
        )
        .where(Survey.well_id == well_id)
        .order_by(Survey.survey.asc())
    ).all()
    
    return [
        SurveyWithDiff(**survey.__dict__, md_diff=md_diff, tvd_diff=tvd_diff)
        for survey, md_diff, tvd_diff in results
    ]