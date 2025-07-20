import secrets
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings
from app.utils.jwt_manager import create_access_token, create_refresh_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

router = APIRouter()
oauth = OAuth()

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@router.get('/login')
async def login(request: Request):
    redirect_uri = settings.REDIRECT_URL
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/callback')
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate credentials')
    
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User info not found in token')

    # Here you would typically save the user to your database
    # For this example, we'll create tokens with the user's email
    jwt_payload = {"sub": user_info['email']}
    access_token = create_access_token(data=jwt_payload)
    refresh_token = create_refresh_token(data=jwt_payload)

    # Redirect to frontend, setting tokens in secure cookies
    response = RedirectResponse(url=settings.FRONTEND_URL)

    # Set refresh token in a secure HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # Use True in production
        samesite="lax",
        max_age=60 * 60 * 24 * REFRESH_TOKEN_EXPIRE_DAYS
    )

    # Set access token in a regular cookie for the frontend to read
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False, # Frontend needs to read this
        secure=True,  # Use True in production
        samesite="lax",
        max_age=60 * ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return response

# This scheme will look for a token in the Authorization header (Bearer <token>)
bearer_scheme = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    """
    Dependency function to secure routes.
    It verifies the token and returns the user's email.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token=credentials.credentials, credentials_exception=credentials_exception)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type, expected access")
    return payload.get("sub")


@router.get("/me", summary="Get current user info")
async def read_users_me(current_user_email: str = Depends(get_current_user)):
    """
    A protected route that requires a valid JWT token.
    It returns the email of the authenticated user.
    """
    return {"email": current_user_email}




@router.post("/refresh", summary="Refresh access token")
async def refresh_token_endpoint(response: Response, refresh_token: str | None = Cookie(default=None)):
    """
    Takes a valid refresh token and returns a new access token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")

    refresh_payload = verify_token(token=refresh_token, credentials_exception=credentials_exception)
    
    if refresh_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type, expected refresh")
    
    email = refresh_payload.get("sub")
    new_access_token = create_access_token(data={"sub": email})
    
    # Set the new access token in a readable cookie for the frontend
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=False,
        secure=True, # Use True in production
        samesite="lax",
        max_age=60 * ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return {"access_token": new_access_token, "token_type": "bearer"}
