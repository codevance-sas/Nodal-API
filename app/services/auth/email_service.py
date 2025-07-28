import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class EmailService:
    """
    Service for sending emails, particularly for authentication tokens.
    """
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.allowed_domains = settings.ALLOWED_EMAIL_DOMAINS
    
    def is_domain_allowed(self, email: str) -> bool:
        """
        Check if the email domain is in the allowed domains list.
        
        Args:
            email: The email address to check
            
        Returns:
            True if the domain is allowed, False otherwise
        """
        if not self.allowed_domains:  # If no domains are specified, all are allowed
            return True
            
        domain = email.split('@')[-1].lower()
        return domain in self.allowed_domains
    
    async def send_token_email(self, to_email: str, token: str) -> bool:
        """
        Send an email with an authentication token.
        
        Args:
            to_email: The recipient's email address
            token: The authentication token
            
        Returns:
            True if the email was sent successfully, False otherwise
        """
        if not self.is_domain_allowed(to_email):
            logger.warning(f"Attempted to send token to non-allowed domain: {to_email}")
            return False
            
        subject = f"{settings.PROJECT_NAME} - Your Authentication Token"
        
        # Create HTML content
        html_content = f"""
        <html>
        <body>
            <h2>Your Authentication Token</h2>
            <p>Here is your authentication token for {settings.PROJECT_NAME}:</p>
            <p style="font-size: 18px; font-weight: bold; padding: 10px; background-color: #f0f0f0;">{token}</p>
            <p>This token will expire in 2 days.</p>
            <p>If you did not request this token, please ignore this email.</p>
        </body>
        </html>
        """
        
        # Create plain text content
        text_content = f"""
        Your Authentication Token
        
        Here is your authentication token for {settings.PROJECT_NAME}:
        
        {token}
        
        This token will expire in 2 days.
        
        If you did not request this token, please ignore this email.
        """
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = to_email
        
        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        message.attach(part1)
        message.attach(part2)
        
        try:
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                # Send email
                server.sendmail(self.from_email, to_email, message.as_string())
                
            logger.info(f"Authentication token email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send authentication token email: {str(e)}")
            return False

# Create a singleton instance
email_service = EmailService()