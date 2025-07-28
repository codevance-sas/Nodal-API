import logging
import secrets
from typing import Optional, Tuple, List

from fastapi import HTTPException, Response, status, Depends
from sqlmodel import Session

from app.core.config import settings
from app.services.auth.token_service import token_service
from app.services.auth.password_service import password_service
from app.services.auth.email_service import email_service
from app.db.session import session
from app.crud.auth_tokens import auth_token_crud
from app.crud.users import user_crud
from app.models.auth_token import AuthToken
from app.models.user import User, UserRole

# Configure logging
logger = logging.getLogger(__name__)

class AuthService:
    """
    Service for handling authentication flows including email token authentication,
    session management, and user authentication. This service encapsulates all 
    authentication-related logic to improve separation of concerns.
    """
    
    def __init__(self):
        # No initialization needed
        pass
    
    # OAuth methods have been removed as part of the authentication system refactoring
    
    def set_auth_cookies(self, response: Response, access_token: str, refresh_token: str) -> str:
        """
        Sets authentication cookies on the response.
        
        Args:
            response: The FastAPI response object
            access_token: The JWT access token
            refresh_token: The JWT refresh token
            
        Returns:
            CSRF token for CSRF protection
        """
        # Set refresh token in a secure HttpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.ENV == "production",  # Secure in production
            samesite="lax",
            max_age=60 * 60 * 24 * token_service.refresh_token_expire_days,
            path="/api/auth"  # Restrict to auth endpoints
        )
        
        # Set access token in a secure cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,  # Frontend needs to read this
            secure=settings.ENV == "production",  # Secure in production
            samesite="lax",
            max_age=60 * token_service.access_token_expire_minutes
        )
        
        # Set CSRF token for protection against CSRF attacks
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,  # Frontend needs to read this
            secure=settings.ENV == "production",
            samesite="lax",
            max_age=60 * 60 * 24  # 1 day
        )
        
        return csrf_token
    
    def clear_auth_cookies(self, response: Response) -> None:
        """
        Clears authentication cookies from the response.
        
        Args:
            response: The FastAPI response object
        """
        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token", path="/api/auth")
        response.delete_cookie(key="csrf_token")
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Creates a new access token from a refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New access token
            
        Raises:
            HTTPException: If refresh token is invalid
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        # Verify the refresh token
        refresh_payload = token_service.verify_token(
            token=refresh_token, 
            credentials_exception=credentials_exception
        )
        
        # Ensure it's a refresh token
        if refresh_payload.get("type") != "refresh":
            logger.warning(f"Invalid token type: {refresh_payload.get('type')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token type, expected refresh token"
            )
        
        # Create a new access token
        email = refresh_payload.get("sub")
        new_access_token = token_service.create_access_token(data={
            "sub": email,
            "name": refresh_payload.get("name", ""),
            "picture": refresh_payload.get("picture", "")
        })
        
        return new_access_token
    
    def validate_csrf_token(self, cookie_token: Optional[str], header_token: Optional[str]) -> None:
        """
        Validates CSRF token.
        
        Args:
            cookie_token: CSRF token from cookie
            header_token: CSRF token from header
            
        Raises:
            HTTPException: If CSRF validation fails
        """
        if not cookie_token or not header_token or cookie_token != header_token:
            logger.warning("CSRF token validation failed")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed"
            )
            
    async def request_email_token(self, email: str, db: Session) -> Tuple[bool, str]:
        """
        Request an authentication token to be sent via email.
        
        Args:
            email: The email address to send the token to
            db: Database session
            
        Returns:
            Tuple of (success, message)
        """
        return await token_service.generate_email_token(email, db)
        
    def validate_email_token(self, token: str, db: Session) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Validate an email token and create JWT tokens if valid.
        
        Args:
            token: The token to validate
            db: Database session
            
        Returns:
            Tuple of (success, message, access_token, refresh_token)
        """
        # Verify the email token
        email = token_service.verify_email_token(token, db)
        
        if not email:
            return False, "Invalid or expired token", None, None
            
        # Create JWT payload with user information
        jwt_payload = {
            "sub": email,
            "name": f"User ({email})",
            "picture": ""
        }
        
        # Create tokens
        try:
            access_token = token_service.create_access_token(data=jwt_payload)
            refresh_token = token_service.create_refresh_token(data=jwt_payload)
            return True, "Token validated successfully", access_token, refresh_token
        except Exception as e:
            logger.error(f"Token creation failed: {str(e)}")
            return False, "Failed to create authentication tokens", None, None
            
    async def admin_generate_token(self, email: str, db: Session) -> Tuple[bool, str]:
        """
        Generate a token for an email as an admin, bypassing normal restrictions.
        
        Args:
            email: The email address to generate a token for
            db: Database session
            
        Returns:
            Tuple of (success, message)
        """
        return await token_service.generate_email_token(email, db, is_admin_generated=True)
        
    def get_all_tokens(self, db: Session, skip: int = 0, limit: int = 100) -> List[AuthToken]:
        """
        Get all auth tokens with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of AuthToken instances
        """
        return auth_token_crud.get_all_tokens(db, skip, limit)
    
    def register_user(self, email: str, password: str, db: Session) -> Tuple[bool, str, Optional[User]]:
        """
        Register a new user with password-based authentication.
        
        Args:
            email: User's email address
            password: User's password (plain text)
            db: Database session
            
        Returns:
            Tuple of (success, message, user)
        """
        try:
            # Check if the email domain is allowed
            if not email_service.is_domain_allowed(email):
                return False, "Email domain not allowed", None
                
            # Check if a user with this email already exists
            existing_user = user_crud.get_user_by_email(db, email)
            if existing_user:
                return False, "A user with this email already exists", None
                
            # Hash the password
            password_hash = password_service.hash_password(password)
            
            # Create the user with USER role
            user = user_crud.create_user(db, email, password_hash, UserRole.USER)
            
            return True, "User registered successfully", user
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            return False, "An error occurred during registration", None
    
    def login_user(self, email: str, password: str, db: Session) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Login a user with password-based authentication.
        
        Args:
            email: User's email address
            password: User's password (plain text)
            db: Database session
            
        Returns:
            Tuple of (success, message, access_token, refresh_token)
        """
        try:
            # Get the user by email
            user = user_crud.get_user_by_email(db, email)
            
            # Check if the user exists
            if not user:
                return False, "Invalid email or password", None, None
                
            # Check if the user is active
            if not user.is_active:
                return False, "User account is inactive", None, None
                
            # Verify the password
            if not password_service.verify_password(password, user.password_hash):
                return False, "Invalid email or password", None, None
                
            # Create JWT payload with user information
            jwt_payload = {
                "sub": user.email,
                "name": f"User ({user.email})",
                "picture": "",
                "role": user.role
            }
            
            # Create tokens
            access_token = token_service.create_access_token(data=jwt_payload)
            refresh_token = token_service.create_refresh_token(data=jwt_payload)
            
            return True, "Login successful", access_token, refresh_token
        except Exception as e:
            logger.error(f"Error logging in user: {str(e)}")
            return False, "An error occurred during login", None, None
    
    def get_user_by_email(self, email: str, db: Session) -> Optional[User]:
        """
        Get a user by email.
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            User instance if found, None otherwise
        """
        return user_crud.get_user_by_email(db, email)
    
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
        return user_crud.get_users(db, skip, limit)
    
    def set_user_role(self, user: User, role: UserRole, db: Session) -> User:
        """
        Set a user's role.
        
        Args:
            user: User instance to update
            role: New role
            db: Database session
            
        Returns:
            Updated User instance
        """
        return user_crud.set_user_role(db, user, role)

# Create a singleton instance
auth_service = AuthService()