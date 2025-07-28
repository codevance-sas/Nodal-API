import logging
from typing import Generator, List, Set
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from sqlalchemy import inspect

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

def create_db_and_tables():
    """Create only the database tables that don't exist yet"""
    try:
        # Get inspector to check existing tables
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        
        # Get all tables defined in SQLModel metadata
        metadata_tables = set(SQLModel.metadata.tables.keys())
        
        # Find tables that need to be created (in metadata but not in database)
        tables_to_create = metadata_tables - existing_tables
        
        if not tables_to_create:
            logger.info("All tables already exist in the database")
            return
            
        # Create only the tables that don't exist
        for table_name in tables_to_create:
            if table_name in SQLModel.metadata.tables:
                table = SQLModel.metadata.tables[table_name]
                table.create(engine)
                logger.info(f"Created table: {table_name}")
        
        logger.info(f"Created {len(tables_to_create)} new tables")
    except SQLAlchemyError as e:
        logger.error(f"Error creating database tables: {e}")
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












