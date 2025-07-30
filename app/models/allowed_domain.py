from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, DateTime, func

class AllowedDomain(SQLModel, table=True):
    """
    Model for storing allowed email domains for token generation.
    This allows managing which email domains are allowed to request authentication tokens.
    """
    __tablename__ = "allowed_domains"
    
    domain: str = Field(primary_key=True, index=True)
    created_at: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    description: Optional[str] = Field(default=None)
    
    @classmethod
    def create(cls, domain: str, description: Optional[str] = None):
        """
        Create a new allowed domain record.
        
        Args:
            domain: The domain name (e.g., "example.com")
            description: Optional description or purpose of this domain
            
        Returns:
            A new AllowedDomain instance
        """
        return cls(
            domain=domain.lower().strip(),
            description=description
        )