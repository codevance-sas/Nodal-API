import logging
import traceback
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.utils.error_handling import APIError, handle_api_error
from app.utils.response_formatter import response_formatter

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling exceptions and providing consistent error responses.
    
    This middleware catches exceptions raised during request processing and
    converts them to standardized error responses using the error handling utilities.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process the request and handle any exceptions.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response from the next middleware or route handler,
            or a standardized error response if an exception occurs
        """
        try:
            return await call_next(request)
        except APIError as e:
            # For our custom API errors, use their status code and details
            logger.warning(f"API error: {e.error_code} - {e.message}")
            return JSONResponse(
                status_code=e.status_code,
                content=response_formatter.error(
                    message=e.message,
                    error_code=e.error_code,
                    details=e.details
                )
            )
        except Exception as e:
            # For unexpected errors, log the full traceback and return a generic error
            tb = traceback.format_exc()
            logger.error(f"Unexpected error: {str(e)}\n{tb}")
            
            return JSONResponse(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                content=response_formatter.error(
                    message="An unexpected error occurred",
                    error_code="internal_error",
                    details={"error_type": type(e).__name__}
                )
            )