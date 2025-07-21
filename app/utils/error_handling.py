# app/utils/error_handling.py

import logging
import traceback
from typing import Dict, Any, Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base class for API errors"""
    def __init__(
        self, 
        message: str, 
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "internal_error",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class ValidationError(APIError):
    """Error for validation failures"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="validation_error",
            details=details
        )

class AuthenticationError(APIError):
    """Error for authentication failures"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="authentication_error",
            details=details
        )

class AuthorizationError(APIError):
    """Error for authorization failures"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="authorization_error",
            details=details
        )

class NotFoundError(APIError):
    """Error for resource not found"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="not_found",
            details=details
        )

class CalculationError(APIError):
    """Error for calculation failures"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="calculation_error",
            details=details
        )

def handle_api_error(error: Exception) -> HTTPException:
    """
    Convert any exception to an appropriate HTTPException.
    This provides consistent error handling across the application.
    
    Args:
        error: The exception to handle
        
    Returns:
        HTTPException with appropriate status code and details
    """
    if isinstance(error, APIError):
        # For our custom API errors, use their status code and details
        return HTTPException(
            status_code=error.status_code,
            detail={
                "error": error.error_code,
                "message": error.message,
                "details": error.details
            }
        )
    elif isinstance(error, HTTPException):
        # For FastAPI's HTTPException, just return it
        return error
    else:
        # For unexpected errors, log the full traceback and return a generic error
        tb = traceback.format_exc()
        logger.error(f"Unexpected error: {str(error)}\n{tb}")
        
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "details": {"error_type": type(error).__name__}
            }
        )

def error_response(
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    error_code: str = "internal_error",
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.
    
    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Error code for the client
        details: Additional error details
        
    Returns:
        Standardized error response dictionary
    """
    return {
        "error": error_code,
        "message": message,
        "status_code": status_code,
        "details": details or {}
    }