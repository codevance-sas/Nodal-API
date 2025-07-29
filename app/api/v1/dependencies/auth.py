import logging
from typing import Optional, List

from fastapi import Depends, HTTPException, Cookie, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth.token_service import token_service
from app.services.auth.auth_service import auth_service
from app.core.config import settings
from app.models.user import UserRole

# Configure logging
logger = logging.getLogger(__name__)

# Bearer token authentication scheme
bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> dict:
    """
    Dependency function to secure routes.
    It verifies the token and returns the user's information.
    Only supports Authorization header authentication.
    
    Args:
        credentials: Bearer token credentials from Authorization header
        
    Returns:
        Dictionary with user information (email, role)
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check for token in Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    
    if not token:
        logger.warning("No authentication token provided")
        raise credentials_exception
    
    # Verify the token
    try:
        payload = token_service.verify_token(token=token, credentials_exception=credentials_exception)
        
        # Ensure it's an access token
        if payload.get("type") != "access":
            logger.warning(f"Invalid token type: {payload.get('type')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token type, expected access token"
            )
        
        # Get user information from the token
        email = payload.get("sub")
        role = payload.get("role", UserRole.USER)  # Default to USER if role not in token
        
        return {"email": email, "role": role}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in authentication: {str(e)}")
        raise credentials_exception

async def get_super_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency function to secure admin routes.
    It verifies that the authenticated user is the super user.
    
    Args:
        current_user: User information from get_current_user
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If the user is not the super user
    """
    if current_user["email"] != settings.SUPER_USER_EMAIL:
        logger.warning(f"Unauthorized access attempt to admin endpoint by {current_user['email']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this endpoint. Only the super user can access admin endpoints."
        )
    
    return current_user

async def get_admin_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency function to secure admin routes.
    It verifies that the authenticated user has the ADMIN role.
    
    Args:
        current_user: User information from get_current_user
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If the user does not have the ADMIN role
    """
    if current_user["role"] != UserRole.ADMIN:
        logger.warning(f"Unauthorized access attempt to admin endpoint by {current_user['email']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this endpoint. Only admin users can access admin endpoints."
        )
    
    return current_user

def check_role(allowed_roles: List[UserRole]):
    """
    Factory function to create a dependency that checks if the user has one of the allowed roles.
    
    Args:
        allowed_roles: List of roles that are allowed to access the endpoint
        
    Returns:
        Dependency function that checks if the user has one of the allowed roles
    """
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        """
        Dependency function to check if the user has one of the allowed roles.
        
        Args:
            current_user: User information from get_current_user
            
        Returns:
            User information dictionary
            
        Raises:
            HTTPException: If the user does not have one of the allowed roles
        """
        if current_user["role"] not in allowed_roles:
            logger.warning(f"Unauthorized access attempt by {current_user['email']} with role {current_user['role']}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized to access this endpoint. Required roles: {', '.join(allowed_roles)}"
            )
        
        return current_user
    
    return role_checker