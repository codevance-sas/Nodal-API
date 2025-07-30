from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserTokenResponse(BaseModel):
    """
    Schema for user's token response.
    """
    email: str
    created_at: datetime
    expires_at: datetime
    is_used: bool
    is_admin_generated: bool
    active: bool  # Indicates if the token is still valid (not expired)

class TokenRevokeResponse(BaseModel):
    """
    Schema for token revocation response.
    """
    success: bool
    message: str