# app/utils/response_formatter.py

from typing import Dict, Any, List, Optional, Union, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard response format for paginated data.
    
    Attributes:
        items: List of items in the current page
        total: Total number of items across all pages
        page: Current page number (1-based)
        page_size: Number of items per page
        pages: Total number of pages
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

class StandardResponse(BaseModel, Generic[T]):
    """
    Standard response format for API responses.
    
    Attributes:
        status: Response status ("success" or "error")
        data: Response data (for successful responses)
        error: Error details (for error responses)
        message: Optional message
        metadata: Optional metadata
    """
    status: str
    data: Optional[T] = None
    error: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

def success_response(
    data: Any = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Optional success message
        metadata: Optional metadata
        
    Returns:
        Standardized success response dictionary
    """
    response = {
        "status": "success",
        "data": data
    }
    
    if message:
        response["message"] = message
        
    if metadata:
        response["metadata"] = metadata
        
    return response

def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized paginated response.
    
    Args:
        items: List of items in the current page
        total: Total number of items across all pages
        page: Current page number (1-based)
        page_size: Number of items per page
        metadata: Optional metadata
        
    Returns:
        Standardized paginated response dictionary
    """
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    response = {
        "status": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages
        }
    }
    
    if metadata:
        response["metadata"] = metadata
        
    return response

def error_response(
    message: str,
    error_code: str = "internal_error",
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        error_code: Error code for the client
        details: Additional error details
        
    Returns:
        Standardized error response dictionary
    """
    return {
        "status": "error",
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        }
    }

# Create a singleton instance for easy access
class ResponseFormatter:
    """
    Utility class for formatting API responses.
    """
    
    @staticmethod
    def success(
        data: Any = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized success response.
        
        Args:
            data: Response data
            message: Optional success message
            metadata: Optional metadata
            
        Returns:
            Standardized success response dictionary
        """
        return success_response(data, message, metadata)
    
    @staticmethod
    def paginated(
        items: List[Any],
        total: int,
        page: int,
        page_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized paginated response.
        
        Args:
            items: List of items in the current page
            total: Total number of items across all pages
            page: Current page number (1-based)
            page_size: Number of items per page
            metadata: Optional metadata
            
        Returns:
            Standardized paginated response dictionary
        """
        return paginated_response(items, total, page, page_size, metadata)
    
    @staticmethod
    def error(
        message: str,
        error_code: str = "internal_error",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            message: Error message
            error_code: Error code for the client
            details: Additional error details
            
        Returns:
            Standardized error response dictionary
        """
        return error_response(message, error_code, details)

response_formatter = ResponseFormatter()