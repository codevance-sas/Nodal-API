import logging
from typing import Generator
from sqlmodel import create_engine, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
import os

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create database engine with connection pooling
engine_args = {
    "pool_pre_ping": True,  # Enable connection health checks
    "pool_recycle": 300,    # Recycle connections after 5 minutes
    "pool_size": 5,         # Default pool size
    "max_overflow": 10,     # Allow up to 10 connections beyond pool_size
    "poolclass": QueuePool,
    "connect_args": {
        # Enable SSL in production
        **({"sslmode": "require"} if settings.ENV == "production" else {})
    }
}

# Create engine with proper error handling
try:
    engine = create_engine(str(settings.DATABASE_URI), **engine_args)
    logger.info(f"Connected to database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
except Exception as e:
    logger.error(f"Failed to connect to database: {e}")
    raise

def session() -> Generator[Session, None, None]:
    """
    Dependency function that yields a SQLModel session
    """
    db_session = Session(engine)
    try:
        yield db_session
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()

if __name__ == "__main__":
    # Import here to avoid circular imports
    from app.db.migrations import create_db_and_tables
    create_db_and_tables()












