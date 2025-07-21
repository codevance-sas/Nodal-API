import logging
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status, Header
from fastapi.responses import RedirectResponse
from typing import Optional, Dict, Any

from app.core.config import settings
from app.services.auth.auth_service import auth_service
from app.services.auth.token_service import token_service
from app.api.v1.dependencies.auth import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get('/login')
async def login(request: Request):
    """
    Initiates the OAuth login flow with Google.
    Redirects the user to Google's authentication page.
    """
    return await auth_service.initiate_oauth_flow(request)

@router.get('/callback')
async def auth(request: Request):
    """
    Handles the OAuth callback from Google.
    Validates the authentication and creates JWT tokens.
    """
    try:
        # Handle OAuth callback and get tokens
        user_info, access_token, refresh_token = await auth_service.handle_oauth_callback(request)
        
        # Redirect to frontend with tokens in secure cookies
        response = RedirectResponse(url=settings.FRONTEND_URL)
        
        # Set authentication cookies
        auth_service.set_auth_cookies(response, access_token, refresh_token)
        
        return response
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in authentication callback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )

@router.get("/me", summary="Get current user info")
async def read_users_me(current_user_email: str = Depends(get_current_user)):
    """
    A protected route that requires a valid JWT token.
    It returns the email of the authenticated user.
    """
    return {"email": current_user_email}

@router.get("/test-auth", summary="Test authentication")
async def test_auth(current_user_email: str = Depends(get_current_user)):
    """
    A simple endpoint to test if authentication is working correctly.
    If you can see the response, your authentication is working!
    
    This is useful for testing tokens obtained from the /dev-token endpoint.
    """
    return {
        "message": "Authentication successful!",
        "email": current_user_email,
        "authenticated": True,
        "timestamp": str(import_time())
    }

# Helper function to get current time
def import_time():
    from datetime import datetime
    return datetime.now()

@router.post("/refresh", summary="Refresh access token")
async def refresh_token_endpoint(
    response: Response, 
    refresh_token: Optional[str] = Cookie(default=None),
    csrf_token: Optional[str] = Cookie(default=None),
    x_csrf_token: Optional[str] = Header(default=None)
):
    """
    Takes a valid refresh token and returns a new access token.
    Requires CSRF token validation.
    """
    try:
        # Validate CSRF token
        auth_service.validate_csrf_token(csrf_token, x_csrf_token)
        
        if not refresh_token:
            logger.warning("Refresh token not found in request")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Refresh token not found"
            )
        
        # Create new access token
        new_access_token = auth_service.refresh_access_token(refresh_token)
        
        # Set the new access token in a cookie
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=False,
            secure=settings.ENV == "production",
            samesite="lax",
            max_age=60 * auth_service.token_service.access_token_expire_minutes
        )
        
        # Generate a new CSRF token
        new_csrf_token = auth_service.set_auth_cookies(
            response, 
            new_access_token, 
            refresh_token
        )
        
        return {
            "access_token": new_access_token, 
            "token_type": "bearer",
            "csrf_token": new_csrf_token
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while refreshing the token"
        )

@router.post("/logout", summary="Logout user")
async def logout(response: Response):
    """
    Logs out the user by clearing authentication cookies.
    """
    auth_service.clear_auth_cookies(response)
    return {"message": "Successfully logged out"}

@router.post("/dev-token", summary="Generate tokens for development/testing")
async def generate_dev_token(email: str, response: Response):
    """
    Generates access and refresh tokens for development and testing purposes.
    This endpoint is only available in development mode.
    
    - **email**: Email to use as the subject of the token
    
    Returns both tokens directly in the response body and also sets them as cookies.
    """
    # Only available in development mode
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )
    
    try:
        # Create token payload
        token_data = {
            "sub": email,
            "name": f"Test User ({email})",
            "picture": ""
        }
        
        # Generate tokens
        access_token = token_service.create_access_token(data=token_data)
        refresh_token = token_service.create_refresh_token(data=token_data)
        
        # Set cookies for convenience
        csrf_token = auth_service.set_auth_cookies(response, access_token, refresh_token)
        
        # Return tokens directly in response body for easy copying
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "csrf_token": csrf_token,
            "user": {
                "email": email,
                "name": f"Test User ({email})"
            },
            "note": "These tokens are for development/testing only. Copy the access_token for use with Swagger UI."
        }
    except Exception as e:
        logger.error(f"Error generating development tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate tokens"
        )