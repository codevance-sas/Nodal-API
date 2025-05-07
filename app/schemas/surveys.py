from app.models.survey import Survey
class SurveyWithDiff(Survey):
    md_diff: float | None
    tvd_diff: float | None