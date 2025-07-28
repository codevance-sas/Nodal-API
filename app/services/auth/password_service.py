import logging
from passlib.context import CryptContext

# Configure logging
logger = logging.getLogger(__name__)

class PasswordService:
    """
    Service for handling password hashing and verification.
    Uses passlib's CryptContext for secure password hashing.
    """
    
    def __init__(self):
        # Configure the password hashing context
        # Using bcrypt algorithm with default parameters
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to verify against
            
        Returns:
            True if the password matches the hash, False otherwise
        """
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False

# Create a singleton instance
password_service = PasswordService()