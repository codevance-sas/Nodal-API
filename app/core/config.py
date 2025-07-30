import os
import secrets
from typing import Any, List, Optional, Union
from pydantic import PostgresDsn, field_validator, ValidationInfo
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()



class Settings(BaseSettings):
    # CORE SETTINGS
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = ENV == "development"
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Nodal API"
    
    # SECURITY SETTINGS
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    AUTH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("AUTH_TOKEN_EXPIRE_DAYS", "2"))
    
    # EMAIL SETTINGS
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@example.com")
    ALLOWED_EMAIL_DOMAINS: List[str] = []
    
    @field_validator("ALLOWED_EMAIL_DOMAINS", mode="before")
    def parse_allowed_domains(cls, v: Optional[str]) -> List[str]:
        if isinstance(v, str):
            return [domain.strip().lower() for domain in v.split(",") if domain.strip()]
        return []
    
    # CORS SETTINGS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://nodal-app.vercel.app"
    ]

    @field_validator("BACKEND_CORS_ORIGINS")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # AUTHENTICATION SETTINGS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    SUPER_USER_EMAIL: str = os.getenv("SUPER_USER_EMAIL", "admin@example.com")
    
    # DATABASE SETTINGS
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "nodal")
    
    # Build DATABASE_URI using the class variables that were loaded with os.getenv()
    DATABASE_URI: Optional[PostgresDsn] = PostgresDsn.build(
        scheme="postgresql+psycopg2",
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        path=f"{os.getenv('DB_NAME', 'nodal')}"
    )
    
    # LOGGING SETTINGS
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
