import os
import secrets
from typing import Any, List, Optional, Union
from pydantic import PostgresDsn, field_validator, ValidationInfo
from pydantic_settings import BaseSettings


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
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    REDIRECT_URL: str = os.getenv("REDIRECT_URL", "http://localhost:8000/api/auth/callback")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # DATABASE SETTINGS
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "nodal")
    DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URI")
    def assemble_db_connection(cls, v: Optional[str], values: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+psycopg2",
            username=values.data.get("DB_USER"),
            password=values.data.get("DB_PASSWORD"),
            host=values.data.get("DB_HOST"),
            port=int(values.data.get("DB_PORT")),
            path=f"{values.data.get('DB_NAME')}"
        )
    
    # LOGGING SETTINGS
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
