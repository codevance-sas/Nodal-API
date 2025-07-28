from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List

class UserCreate(BaseModel):
    """
    Schema for creating a new user with password-based authentication.
    """
    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str
    
    @validator('password_confirm')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class AdminCheckResponse(BaseModel):
    """
    Schema for admin check response.
    """
    admin_exists: bool
    message: str
    user: Optional[Dict[str, Any]] = None

class UserLogin(BaseModel):
    """
    Schema for user login with password-based authentication.
    """
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """
    Schema for user response without sensitive information.
    """
    email: EmailStr
    role: str
    is_active: bool

class TokenResponse(BaseModel):
    """
    Schema for token response.
    """
    success: bool
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[Dict[str, Any]] = None

class EmailRequest(BaseModel):
    """
    Schema for requesting an email token.
    """
    email: EmailStr

class TokenRequest(BaseModel):
    """
    Schema for validating an email token.
    """
    token: str

class AdminTokenRequest(BaseModel):
    """
    Schema for admin generating a token for a user.
    """
    email: EmailStr
    is_admin: bool = False

class TokenListResponse(BaseModel):
    """
    Schema for listing tokens.
    """
    tokens: List[Dict[str, Any]]
    total: int