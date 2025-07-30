import logging
import time
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.api.v1.routes import auth_router, protected_api_router
from app.api.v1.routes.auth import get_current_user
from app.core.config import settings
from app.db.migrations import create_db_and_tables
import app.models  # Import all models to ensure they are registered with SQLModel.metadata

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Custom middleware for request logging and timing
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log request details
            logger.info(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Process time: {process_time:.4f}s"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url.path} - "
                f"Error: {str(e)} - "
                f"Process time: {process_time:.4f}s"
            )
            raise

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    API for Nodal Analysis
    
    ## Authentication
    
    This API uses email-based token authentication. The flow is:
    
    1. Request a token by calling `POST /auth/request-token` with your email
    2. Check your email for the token (valid for 2 days)
    3. Validate the token by calling `POST /auth/validate-token` with the token
    4. Use the returned JWT token for authentication
    
    For API testing, you can use the token in the format: `Bearer your_token_here`
    
    1. Copy the `access_token` from the validation response
    2. Click the "Authorize" button at the top of this page
    3. Enter the token in the format: `Bearer your_token_here`
    4. Click "Authorize" and close the dialog
    
    Now all your API requests will include the authentication token.
    
    Note: Only emails with allowed domains can request tokens, and a token cannot be 
    regenerated for the same email until it expires or is used, unless done by an admin.
    """,
    version="1.0.0",
    root_path=settings.API_V1_STR,
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,  # Disable redoc in production
)

# Add session middleware for Google Auth
# IMPORTANT: This must be placed before the routers that use it.
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    max_age=60 * 60 * 24 * 7,  # 7 days
    https_only=settings.ENV == "production",  # HTTPS only in production
)

# Add CORS middleware with settings from config
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-Process-Time"],
)

# Add GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# Include the public authentication router
app.include_router(auth_router)

# Include the protected API router with a global security dependency
app.include_router(
    protected_api_router,
    dependencies=[Depends(get_current_user)]
)

@app.get("/")
def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}
