from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session
from pydantic import BaseModel, EmailStr, Field

from app.db.session import session
from app.models.user import User, UserRole
from app.crud.users import user_crud
from app.schemas.auth import UserResponse
from app.api.v1.dependencies.auth import get_admin_user

# Create router
router = APIRouter()

# Define schemas
class UserUpdate(BaseModel):
    """
    Schema for updating user information.
    """
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserListResponse(BaseModel):
    """
    Schema for listing users with pagination.
    """
    users: List[UserResponse]
    total: int

# Endpoints
@router.get("/", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(session),
    _: dict = Depends(get_admin_user)
):
    """
    List all users with pagination.
    Only accessible by admin users.
    """
    users = user_crud.get_users(db, skip=skip, limit=limit)
    
    # Convert to response model
    user_responses = [
        UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active
        ) for user in users
    ]
    
    return UserListResponse(
        users=user_responses,
        total=len(users)
    )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(session),
    _: dict = Depends(get_admin_user)
):
    """
    Get a specific user by ID.
    Only accessible by admin users.
    """
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active
    )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(session),
    _: dict = Depends(get_admin_user)
):
    """
    Update a user's information.
    Only accessible by admin users.
    """
    # Get the user
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Update the user
    update_data = user_update.dict(exclude_unset=True)
    updated_user = user_crud.update_user(db, user, **update_data)
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        role=updated_user.role,
        is_active=updated_user.is_active
    )

@router.patch("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    db: Session = Depends(session),
    _: dict = Depends(get_admin_user)
):
    """
    Activate a user.
    Only accessible by admin users.
    """
    # Get the user
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Activate the user
    updated_user = user_crud.activate_user(db, user)
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        role=updated_user.role,
        is_active=updated_user.is_active
    )

@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    db: Session = Depends(session),
    _: dict = Depends(get_admin_user)
):
    """
    Deactivate a user.
    Only accessible by admin users.
    """
    # Get the user
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Deactivate the user
    updated_user = user_crud.deactivate_user(db, user)
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        role=updated_user.role,
        is_active=updated_user.is_active
    )

@router.patch("/{user_id}/role", response_model=UserResponse)
async def set_user_role(
    user_id: int,
    role: UserRole,
    db: Session = Depends(session),
    _: dict = Depends(get_admin_user)
):
    """
    Set a user's role.
    Only accessible by admin users.
    """
    # Get the user
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Set the user's role
    updated_user = user_crud.set_user_role(db, user, role)
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        role=updated_user.role,
        is_active=updated_user.is_active
    )