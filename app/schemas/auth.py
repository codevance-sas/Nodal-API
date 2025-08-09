from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime

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
    id: int
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

class AllowedDomainCreate(BaseModel):
    """
    Schema for creating a new allowed domain or email.
    """
    domain: str = Field(..., description="Domain name or email address to allow")
    description: Optional[str] = Field(None, description="Optional description")
    
    @validator('domain')
    @classmethod
    def domain_format(cls, v: str) -> str:
        import re
        v = v.lower().strip()
        
        if '@' in v:
            # Validate as email address
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError('Invalid email address format')
        else:
            # Validate as domain
            domain_pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(domain_pattern, v):
                raise ValueError('Invalid domain format')
        
        return v

class AllowedDomainResponse(BaseModel):
    """
    Schema for allowed domain response.
    """
    domain: str
    created_at: datetime
    description: Optional[str] = None
    is_email: bool = Field(..., description="True if this is an email address, False if it's a domain")
    
    @classmethod
    def from_orm(cls, obj):
        return cls(
            domain=obj.domain,
            created_at=obj.created_at,
            description=obj.description,
            is_email=obj.is_email
        )

class AllowedDomainListResponse(BaseModel):
    """
    Schema for listing allowed domains.
    """
    domains: List[AllowedDomainResponse]
    total: int

class AllowedEmailCreate(BaseModel):
    """
    Schema for creating a new allowed email.
    """
    email: EmailStr
    description: Optional[str] = None

class AllowedEmailResponse(BaseModel):
    """
    Schema for allowed email response.
    """
    email: EmailStr
    created_at: datetime
    description: Optional[str] = None

class AllowedEmailListResponse(BaseModel):
    """
    Schema for listing allowed emails.
    """
    emails: List[AllowedEmailResponse]
    total: int