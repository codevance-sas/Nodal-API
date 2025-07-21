import logging
from typing import Optional

from fastapi import Depends, HTTPException, Cookie, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth.token_service import token_service
from app.services.auth.auth_service import auth_service

# Configure logging
logger = logging.getLogger(__name__)

# Bearer token authentication scheme
bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    access_token: Optional[str] = Cookie(default=None),
    x_csrf_token: Optional[str] = Header(default=None),
    csrf_token: Optional[str] = Cookie(default=None)
) -> str:
    """
    Dependency function to secure routes.
    It verifies the token and returns the user's email.
    Supports both Authorization header and cookie authentication.
    
    Args:
        credentials: Bearer token credentials from Authorization header
        access_token: Access token from cookie
        x_csrf_token: CSRF token from header
        csrf_token: CSRF token from cookie
        
    Returns:
        User email from the token
        
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
    # Fallback to cookie if no Authorization header
    elif access_token:
        # Validate CSRF token when using cookies
        auth_service.validate_csrf_token(csrf_token, x_csrf_token)
        token = access_token
    
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
            
        return payload.get("sub")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in authentication: {str(e)}")
        raise credentials_exception