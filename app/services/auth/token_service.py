import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class TokenService:
    """
    Service for handling JWT token operations including creation, validation, and verification.
    This service encapsulates all token-related logic to improve separation of concerns.
    """
    
    def __init__(self):
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
        self.jwt_secret_key = settings.JWT_SECRET_KEY
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Creates a short-lived access token with standard claims.
        
        Args:
            data: Dictionary containing claims to include in the token
            expires_delta: Optional custom expiration time
            
        Returns:
            JWT token string
        """
        to_encode = self.encode_data(data, expires_delta)
        
        # Encode the token
        try:
            encoded_jwt = jwt.encode(to_encode, self.jwt_secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create access token"
            )

    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Creates a long-lived refresh token with standard claims.
        
        Args:
            data: Dictionary containing claims to include in the token
            expires_delta: Optional custom expiration time
            
        Returns:
            JWT token string
        """

        to_encode = self.encode_data(data, expires_delta)
        
        # Encode the token
        try:
            # Use a different key for refresh tokens for better security
            # In production, consider using a completely different key
            encoded_jwt = jwt.encode(to_encode, self.jwt_secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create refresh token"
            )
    def encode_data(self, data: dict, expires_delta: Optional[timedelta] = None) -> dict:
        to_encode = data.copy()

        # Set expiration time
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)

        # Add standard claims
        jti = str(uuid.uuid4())  # Unique token ID
        iat = datetime.now(timezone.utc)  # Issued at time

        to_encode.update({
            "exp": expire,
            "iat": iat,
            "jti": jti,
            "type": "refresh",
            "iss": "nodal-api"  # Issuer
        })

        return to_encode
    
    def verify_token(self, token: str, credentials_exception: HTTPException) -> Dict[str, Any]:
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
        try:
            # Decode the token
            payload = jwt.decode(
                token, 
                self.jwt_secret_key, 
                algorithms=[self.algorithm],
                options={"verify_signature": True, "verify_exp": True, "verify_aud": False}
            )
            
            # Validate required claims
            if payload.get("sub") is None:
                logger.warning("Token missing 'sub' claim")
                raise credentials_exception
                
            if payload.get("type") is None:
                logger.warning("Token missing 'type' claim")
                raise credentials_exception
                
            if payload.get("jti") is None:
                logger.warning("Token missing 'jti' claim")
                raise credentials_exception
            
            # Validate issuer if present
            if payload.get("iss") and payload.get("iss") != "nodal-api":
                logger.warning(f"Invalid token issuer: {payload.get('iss')}")
                raise credentials_exception
            
            # Check token age (optional additional security)
            if payload.get("iat"):
                issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
                now = datetime.now(timezone.utc)
                max_age = timedelta(days=30)  # Maximum token age regardless of exp
                
                if now - issued_at > max_age:
                    logger.warning(f"Token too old: {now - issued_at}")
                    raise credentials_exception
            
            # In a real production system, you might check a token blacklist here
            # to see if the token has been revoked
            
            return payload
            
        except JWTError as e:
            logger.warning(f"JWT validation error: {e}")
            raise credentials_exception
        except Exception as e:
            logger.error(f"Unexpected error verifying token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing authentication token"
            )

# Create a singleton instance
token_service = TokenService()