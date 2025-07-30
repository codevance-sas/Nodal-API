from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, Column, DateTime, func, Relationship
from pydantic import EmailStr

class UserRole(str, Enum):
    """
    Enum for user roles in the system.
    """
    USER = "user"
    ADMIN = "admin"

class User(SQLModel, table=True):
    """
    Model for user accounts with role-based access control.
    This model supports password-based authentication and different user roles.
    """
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: EmailStr = Field(unique=True, index=True)
    password_hash: str
    role: UserRole = Field(default=UserRole.USER)
    created_at: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    updated_at: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    is_active: bool = Field(default=True)
    
    # Relationships could be added here if needed
    # For example, if you want to link users to auth tokens:
    # auth_tokens: List["AuthToken"] = Relationship(back_populates="user")
    
    @classmethod
    def create(cls, email: EmailStr, password_hash: str, role: UserRole = UserRole.USER):
        """
        Create a new user.
        
        Args:
            email: User's email address
            password_hash: Hashed password
            role: User's role (default: USER)
            
        Returns:
            A new User instance
        """
        now = datetime.now(timezone.utc)
        
        return cls(
            email=email,
            password_hash=password_hash,
            role=role,
            created_at=now,
            updated_at=now,
            is_active=True
        )