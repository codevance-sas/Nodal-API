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
from app.crud.allowed_domains import allowed_domain_crud
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    EmailRequest, TokenRequest, AdminTokenRequest, TokenListResponse,
    AdminCheckResponse, AllowedDomainCreate, AllowedDomainResponse, 
    AllowedDomainListResponse
)
from app.schemas.auth_token import UserTokenResponse, TokenRevokeResponse

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
    tokens, total = auth_service.get_all_tokens(db, skip, limit)
    
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
    
    return TokenListResponse(tokens=token_dicts, total=total)


@router.delete('/admin/token/{email}', response_model=TokenRevokeResponse, summary="Admin revoke user's token")
async def admin_revoke_token(
    email: str,
    current_user: dict = Depends(get_admin_user),  # Only admin users can access this endpoint
    db: Session = Depends(session)
):
    """
    Revoke (delete) an authentication token for a specific user by email.
    This endpoint is only available to users with the ADMIN role.
    """
    try:
        success, message = auth_service.revoke_token(email, db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
        
        return TokenRevokeResponse(success=success, message=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking token for {email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke token for {email}"
        )


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
            id=0,  # Default ID for users not in the database
            email=current_user["email"],
            role=current_user["role"],
            is_active=True
        )
    
    return UserResponse(
        id=user.id,
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
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

@router.post("/refresh", summary="Refresh access token")
async def refresh_token_endpoint(
    response: Response, 
    refresh_token: Optional[str] = Cookie(default=None)
):
    """
    Takes a valid refresh token and returns a new access token.
    """
    try:
        if not refresh_token:
            logger.warning("Refresh token not found in request")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Refresh token not found"
            )
        
        # Create new access token
        new_access_token = auth_service.refresh_access_token(refresh_token)
        
        # Update the refresh token cookie
        auth_service.set_auth_cookies(
            response, 
            new_access_token, 
            refresh_token
        )
        
        return {
            "access_token": new_access_token, 
            "token_type": "bearer"
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

# Allowed Domains Endpoints

@router.get("/allowed-domains", response_model=AllowedDomainListResponse, summary="List all allowed email domains")
async def list_allowed_domains(
    skip: int = 0, 
    limit: int = 100,
    current_user: dict = Depends(get_admin_user),
    db: Session = Depends(session)
):
    """
    List all allowed email domains for token generation.
    Only accessible by admin users.
    """
    try:
        domains = allowed_domain_crud.get_all_domains(db, skip=skip, limit=limit)
        total = allowed_domain_crud.count_domains(db)
        
        return AllowedDomainListResponse(
            domains=[
                AllowedDomainResponse(
                    domain=domain.domain,
                    created_at=domain.created_at,
                    description=domain.description
                ) for domain in domains
            ],
            total=total
        )
    except Exception as e:
        logger.error(f"Error listing allowed domains: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list allowed domains"
        )

@router.post("/allowed-domains", response_model=AllowedDomainResponse, summary="Add a new allowed email domain")
async def add_allowed_domain(
    domain_data: AllowedDomainCreate,
    current_user: dict = Depends(get_admin_user),
    db: Session = Depends(session)
):
    """
    Add a new allowed email domain for token generation.
    Only accessible by admin users.
    """
    try:
        # Check if domain already exists
        existing_domain = allowed_domain_crud.get_domain(db, domain_data.domain)
        if existing_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Domain '{domain_data.domain}' already exists"
            )
        
        # Create new domain
        domain = allowed_domain_crud.create_domain(
            db, 
            domain_data.domain,
            domain_data.description
        )
        
        return AllowedDomainResponse(
            domain=domain.domain,
            created_at=domain.created_at,
            description=domain.description
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding allowed domain: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add allowed domain"
        )

@router.delete("/allowed-domains/{domain}", response_model=Dict[str, Any], summary="Remove an allowed email domain")
async def remove_allowed_domain(
    domain: str,
    current_user: dict = Depends(get_admin_user),
    db: Session = Depends(session)
):
    """
    Remove an allowed email domain from the list.
    Only accessible by admin users.
    """
    try:
        # Check if domain exists
        existing_domain = allowed_domain_crud.get_domain(db, domain)
        if not existing_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain '{domain}' not found"
            )
        
        # Delete domain
        success = allowed_domain_crud.delete_domain(db, domain)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete domain"
            )
        
        return {
            "success": True,
            "message": f"Domain '{domain}' removed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing allowed domain: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove allowed domain"
        )

# Token Management Endpoints

@router.get("/token", response_model=UserTokenResponse, summary="Get current user's token")
async def get_user_token(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(session)
):
    """
    Get the authentication token for the current user.
    This endpoint returns information about the user's email token,
    including whether it's active (not expired).
    """
    try:
        email = current_user["email"]
        token_info = auth_service.get_user_token(email, db)
        
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No token found for this user"
            )
        
        return UserTokenResponse(**token_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user token"
        )

@router.delete("/token", response_model=TokenRevokeResponse, summary="Revoke current user's token")
async def revoke_user_token(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(session)
):
    """
    Revoke (delete) the authentication token for the current user.
    This endpoint allows users to invalidate their email token.
    """
    try:
        email = current_user["email"]
        success, message = auth_service.revoke_token(email, db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
        
        return TokenRevokeResponse(success=success, message=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking user token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke user token"
        )