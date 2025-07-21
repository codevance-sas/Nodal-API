import logging
import secrets
from typing import Dict, Any, Optional, Tuple

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings
from app.services.auth.token_service import token_service

# Configure logging
logger = logging.getLogger(__name__)

class AuthService:
    """
    Service for handling authentication flows including OAuth, session management,
    and user authentication. This service encapsulates all authentication-related
    logic to improve separation of concerns.
    """
    
    def __init__(self):
        self.oauth = OAuth()
        
        # Register OAuth provider
        self.oauth.register(
            name='google',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            client_kwargs={
                'scope': 'openid email profile'
            }
        )
    
    async def initiate_oauth_flow(self, request: Request) -> RedirectResponse:
        """
        Initiates the OAuth login flow with Google.
        
        Args:
            request: The FastAPI request object
            
        Returns:
            RedirectResponse to Google's authentication page
        """
        # Generate and store CSRF state token in session
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        
        redirect_uri = settings.REDIRECT_URL
        return await self.oauth.google.authorize_redirect(request, redirect_uri, state=state)
    
    async def handle_oauth_callback(self, request: Request) -> Tuple[Dict[str, Any], str, str]:
        """
        Handles the OAuth callback from Google.
        Validates the authentication and creates JWT tokens.
        
        Args:
            request: The FastAPI request object
            
        Returns:
            Tuple containing user info, access token, and refresh token
            
        Raises:
            HTTPException: If authentication fails
        """
        # Verify CSRF state token
        callback_state = request.query_params.get('state')
        session_state = request.session.get('oauth_state')
        
        if not callback_state or not session_state or callback_state != session_state:
            logger.warning("CSRF state token validation failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail='Invalid state parameter'
            )
        
        # Clear the state from session
        request.session.pop('oauth_state', None)
        
        try:
            # Exchange authorization code for tokens
            token = await self.oauth.google.authorize_access_token(request)
        except Exception as e:
            logger.error(f"OAuth token exchange failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail='Authentication failed'
            )
        
        # Get user info from token
        user_info = token.get('userinfo')
        if not user_info:
            logger.error("User info not found in OAuth token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail='User info not found'
            )
        
        # Create JWT payload with user information
        jwt_payload = {
            "sub": user_info['email'],
            "name": user_info.get('name', ''),
            "picture": user_info.get('picture', '')
        }
        
        # Create tokens
        try:
            access_token = token_service.create_access_token(data=jwt_payload)
            refresh_token = token_service.create_refresh_token(data=jwt_payload)
            return user_info, access_token, refresh_token
        except Exception as e:
            logger.error(f"Token creation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail='Failed to create authentication tokens'
            )
    
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

# Create a singleton instance
auth_service = AuthService()