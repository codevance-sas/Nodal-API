"""
JWT Manager Module - Wrapper around TokenService

This module provides JWT token management functions by delegating to the TokenService class.
It maintains the same interface for backward compatibility while eliminating code duplication.
"""

import logging
from datetime import timedelta
from typing import Dict, Optional, Any

from fastapi import HTTPException

from app.services.auth.token_service import token_service

# Configure logging
logger = logging.getLogger(__name__)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a short-lived access token with standard claims.
    
    Args:
        data: Dictionary containing claims to include in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
    """
    return token_service.create_access_token(data=data, expires_delta=expires_delta)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a long-lived refresh token with standard claims.
    
    Args:
        data: Dictionary containing claims to include in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
    """
    return token_service.create_refresh_token(data=data, expires_delta=expires_delta)

def verify_token(token: str, credentials_exception: HTTPException) -> Dict[str, Any]:
    """
    Verifies a token and returns its payload.
    Performs comprehensive validation of token claims.
    
    Args:
        token: JWT token string to verify
        credentials_exception: Exception to raise if validation fails
        
    Returns:
        Dictionary containing the token claims
        
    Raises:
        HTTPException: If token validation fails
    """
    return token_service.verify_token(token=token, credentials_exception=credentials_exception)
