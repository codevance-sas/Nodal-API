from typing import List, Optional
from sqlmodel import Session, select
from app.models.user import User, UserRole

class UserCRUD:
    """
    CRUD operations for User model.
    """
    
    def create_user(self, db: Session, email: str, password_hash: str, role: UserRole = UserRole.USER) -> User:
        """
        Create a new user.
        
        Args:
            db: Database session
            email: User's email address
            password_hash: Hashed password
            role: User's role (default: USER)
            
        Returns:
            The created User instance
        """
        user = User.create(email=email, password_hash=password_hash, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Get a user by email.
        
        Args:
            db: Database session
            email: User's email address
            
        Returns:
            User instance if found, None otherwise
        """
        return db.exec(select(User).where(User.email == email)).first()
    
    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            db: Database session
            user_id: User's ID
            
        Returns:
            User instance if found, None otherwise
        """
        return db.get(User, user_id)
    
    def get_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all users with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of User instances
        """
        return db.exec(select(User).offset(skip).limit(limit)).all()
        
    def count_users(self, db: Session) -> int:
        """
        Count all users in the database.
        
        Args:
            db: Database session
            
        Returns:
            Total number of users
        """
        return db.query(User).count()
    
    def update_user(self, db: Session, user: User, **kwargs) -> User:
        """
        Update a user.
        
        Args:
            db: Database session
            user: User instance to update
            **kwargs: Fields to update
            
        Returns:
            Updated User instance
        """
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    def delete_user(self, db: Session, user: User) -> None:
        """
        Delete a user.
        
        Args:
            db: Database session
            user: User instance to delete
        """
        db.delete(user)
        db.commit()
    
    def set_user_role(self, db: Session, user: User, role: UserRole) -> User:
        """
        Set a user's role.
        
        Args:
            db: Database session
            user: User instance to update
            role: New role
            
        Returns:
            Updated User instance
        """
        user.role = role
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    def deactivate_user(self, db: Session, user: User) -> User:
        """
        Deactivate a user.
        
        Args:
            db: Database session
            user: User instance to deactivate
            
        Returns:
            Updated User instance
        """
        user.is_active = False
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    def activate_user(self, db: Session, user: User) -> User:
        """
        Activate a user.
        
        Args:
            db: Database session
            user: User instance to activate
            
        Returns:
            Updated User instance
        """
        user.is_active = True
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

# Create a singleton instance
user_crud = UserCRUD()