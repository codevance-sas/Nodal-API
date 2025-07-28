import logging
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status, Header
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select

from app.core.config import settings
from app.services.auth.auth_service import auth_service
from app.services.auth.token_service import token_service
from app.api.v1.dependencies.auth import get_current_user, get_admin_user
from app.db.session import session
from app.models.user import UserRole, User
from app.crud.users import user_crud
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    EmailRequest, TokenRequest, AdminTokenRequest, TokenListResponse,
    AdminCheckResponse
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post('/register', response_model=Dict[str, Any])
async def register(
    user_data: UserCreate,
    db: Session = Depends(session)
):
    """
    Register a new user with password-based authentication.
    """
    success, message, user = auth_service.register_user(user_data.email, user_data.password, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {
        "success": True,
        "message": message,
        "user": UserResponse(
            email=user.email,
            role=user.role,
            is_active=user.is_active
        ).dict()
    }

@router.post('/login', response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    response: Response,
    db: Session = Depends(session)
):
    """
    Login a user with password-based authentication.
    """
    success, message, access_token, refresh_token = auth_service.login_user(
        login_data.email, login_data.password, db
    )
    
    if not success:
        return TokenResponse(success=False, message=message)
    
    # Set authentication cookies
    csrf_token = auth_service.set_auth_cookies(response, access_token, refresh_token)
    
    # Get user information
    user = auth_service.get_user_by_email(login_data.email, db)
    
    return TokenResponse(
        success=True,
        message=message,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user={
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
    )

@router.post('/request-token', response_model=Dict[str, Any])
async def request_token(
    request: EmailRequest,
    db: Session = Depends(session)
):
    """
    Request an authentication token to be sent via email.
    The token will be valid for 2 days and can be used to authenticate.
    """
    success, message = await auth_service.request_email_token(request.email, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"success": True, "message": message}

@router.post('/validate-token', response_model=TokenResponse)
async def validate_token(
    request: TokenRequest,
    response: Response,
    db: Session = Depends(session)
):
    """
    Validate an email token and create JWT tokens if valid.
    """
    success, message, access_token, refresh_token = auth_service.validate_email_token(request.token, db)
    
    if not success:
        return TokenResponse(success=False, message=message)
    
    # Set authentication cookies
    csrf_token = auth_service.set_auth_cookies(response, access_token, refresh_token)
    
    return TokenResponse(
        success=True,
        message=message,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user={"email": token_service.verify_token(access_token, HTTPException(status_code=401)).get("sub")}
    )

@router.post('/admin/generate-token', response_model=Dict[str, Any])
async def admin_generate_token(
    request: AdminTokenRequest,
    current_user: dict = Depends(get_admin_user),  # Only admin users can access this endpoint
    db: Session = Depends(session)
):
    """
    Generate a token for an email as an admin, bypassing normal restrictions.
    This endpoint is only available to users with the ADMIN role.
    """
    success, message = await auth_service.admin_generate_token(request.email, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"success": True, "message": message}

@router.get('/admin/tokens', response_model=TokenListResponse)
async def get_all_tokens(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_admin_user),  # Only admin users can access this endpoint
    db: Session = Depends(session)
):
    """
    Get all auth tokens with pagination.
    This endpoint is only available to users with the ADMIN role.
    """
    tokens = auth_service.get_all_tokens(db, skip, limit)
    
    # Convert to dictionary representation
    token_dicts = []
    for token in tokens:
        token_dicts.append({
            "email": token.email,
            "created_at": token.created_at,
            "expires_at": token.expires_at,
            "is_used": token.is_used,
            "is_admin_generated": token.is_admin_generated
        })
    
    return TokenListResponse(tokens=token_dicts, total=len(token_dicts))


# OAuth routes have been removed as part of the authentication system refactoring

@router.get("/me", summary="Get current user info", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user), db: Session = Depends(session)):
    """
    A protected route that requires a valid JWT token.
    It returns information about the authenticated user.
    """
    # Get the full user object from the database
    user = auth_service.get_user_by_email(current_user["email"], db)
    
    if not user:
        # If the user doesn't exist in the database yet,
        # return the basic information from the token
        return UserResponse(
            email=current_user["email"],
            role=current_user["role"],
            is_active=True
        )
    
    return UserResponse(
        email=user.email,
        role=user.role,
        is_active=user.is_active
    )

@router.get("/test-auth", summary="Test authentication")
async def test_auth(current_user: dict = Depends(get_current_user)):
    """
    A simple endpoint to test if authentication is working correctly.
    If you can see the response, your authentication is working!
    
    This is useful for testing tokens obtained from the /dev-token endpoint.
    """
    return {
        "message": "Authentication successful!",
        "email": current_user["email"],
        "role": current_user["role"],
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


@router.post("/check-admin", response_model=AdminCheckResponse, summary="Check if admin exists and create one if not")
async def check_admin(
    user_data: Optional[UserCreate] = None,
    db: Session = Depends(session)
):
    """
    Checks if an admin user exists in the system.
    If no admin exists and user data is provided, creates an admin user.
    
    - If admin exists: Returns a message indicating that an admin already exists
    - If no admin exists and no user data provided: Returns a message indicating that no admin exists
    - If no admin exists and user data provided: Creates an admin user and returns success message
    """
    try:
        # Check if any admin user exists
        admin_exists = db.exec(
            select(User).where(User.role == UserRole.ADMIN)
        ).first() is not None
        
        if admin_exists:
            return AdminCheckResponse(
                admin_exists=True,
                message="Admin user already exists"
            )
        
        # No admin exists
        if not user_data:
            return AdminCheckResponse(
                admin_exists=False,
                message="No admin user exists. Provide user data to create one."
            )
        
        # Create admin user
        success, message, user = auth_service.register_user(
            user_data.email, 
            user_data.password, 
            db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Set user role to admin
        user = user_crud.set_user_role(db, user, UserRole.ADMIN)
        
        return AdminCheckResponse(
            admin_exists=True,
            message="Admin user created successfully",
            user={
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking/creating admin user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check/create admin user"
        )