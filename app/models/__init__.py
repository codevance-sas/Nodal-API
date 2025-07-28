# Import all models here to ensure they are registered with SQLModel.metadata
from app.models.survey import Survey, Operator, Well
from app.models.auth_token import AuthToken
from app.models.user import User, UserRole

# Add any new models here