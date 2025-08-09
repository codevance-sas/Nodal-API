from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, DateTime, func

class AllowedDomain(SQLModel, table=True):
    """
    Model for storing allowed email domains and specific email addresses for token generation.
    This allows managing which email domains or specific email addresses are allowed to request authentication tokens.
    The system automatically detects if an entry is an email (contains '@') or a domain.
    """
    __tablename__ = "allowed_domains"
    
    domain: str = Field(primary_key=True, index=True)
    created_at: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    description: Optional[str] = Field(default=None)
    
    @classmethod
    def create(cls, domain: str, description: Optional[str] = None):
        """
        Create a new allowed domain or email record.
        
        Args:
            domain: The domain name (e.g., "example.com") or email address (e.g., "user@example.com")
            description: Optional description or purpose of this domain/email
            
        Returns:
            A new AllowedDomain instance
        """
        return cls(
            domain=domain.lower().strip(),
            description=description
        )
    
    @property
    def is_email(self) -> bool:
        """
        Check if this entry is an email address by detecting '@' symbol.
        
        Returns:
            True if this is an email address, False if it's a domain
        """
        return '@' in self.domain