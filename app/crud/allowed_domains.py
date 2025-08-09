from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.allowed_domain import AllowedDomain

class AllowedDomainCRUD:
    """
    CRUD operations for AllowedDomain model.
    """
    
    @staticmethod
    def create_domain(db: Session, domain: str, description: Optional[str] = None) -> AllowedDomain:
        """
        Create a new allowed domain or email record.
        
        Args:
            db: Database session
            domain: The domain name (e.g., "example.com") or email address (e.g., "user@example.com")
            description: Optional description or purpose of this domain/email
            
        Returns:
            The created AllowedDomain instance
        """
        domain_obj = AllowedDomain.create(
            domain=domain,
            description=description
        )
        
        db.add(domain_obj)
        db.commit()
        db.refresh(domain_obj)
        
        return domain_obj
        
    @staticmethod
    def delete_domain(db: Session, domain: str) -> bool:
        """
        Delete an allowed domain record.
        
        Args:
            db: Database session
            domain: The domain name to delete
            
        Returns:
            True if a domain was deleted, False otherwise
        """
        result = db.query(AllowedDomain).filter(AllowedDomain.domain == domain.lower().strip()).delete()
        db.commit()
        
        return result > 0
    
    @staticmethod
    def get_domain(db: Session, domain: str) -> Optional[AllowedDomain]:
        """
        Get an allowed domain record by domain name.
        
        Args:
            db: Database session
            domain: The domain name to look up
            
        Returns:
            The AllowedDomain instance if found, None otherwise
        """
        return db.query(AllowedDomain).filter(AllowedDomain.domain == domain.lower().strip()).first()
    
    @staticmethod
    def get_all_domains(db: Session, skip: int = 0, limit: int = 100) -> List[AllowedDomain]:
        """
        Get all allowed domains with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of AllowedDomain instances
        """
        return db.query(AllowedDomain).offset(skip).limit(limit).all()
        
    @staticmethod
    def count_domains(db: Session) -> int:
        """
        Count all allowed domains in the database.
        
        Args:
            db: Database session
            
        Returns:
            Total number of allowed domains
        """
        return db.query(AllowedDomain).count()
    
    @staticmethod
    def is_domain_allowed(db: Session, email: str) -> bool:
        """
        Check if an email address is allowed based on domain or specific email rules.
        
        Args:
            db: Database session
            email: Email address to check
            
        Returns:
            True if the email is allowed, False otherwise
        """
        # If no domains/emails are configured, allow all
        if AllowedDomainCRUD.count_domains(db) == 0:
            return True
            
        email = email.lower().strip()
        
        # Get all allowed entries
        allowed_entries = db.query(AllowedDomain).all()
        
        for entry in allowed_entries:
            if entry.is_email:
                # Check if the specific email is allowed
                if entry.domain == email:
                    return True
            else:
                # Check if the domain is allowed
                domain = email.split('@')[1] if '@' in email else email
                if entry.domain == domain:
                    return True
        
        return False

# Create a singleton instance
allowed_domain_crud = AllowedDomainCRUD()