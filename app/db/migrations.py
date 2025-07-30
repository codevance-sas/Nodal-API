import logging
import os
from typing import Dict, Any, List
from sqlalchemy.exc import SQLAlchemyError
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from app.db.session import engine
from app.db.alembic_helpers import upgrade_database, get_current_revision, get_migration_history

# Configure logging
logger = logging.getLogger(__name__)

def create_db_and_tables() -> Dict[str, Any]:
    """
    Apply any pending database migrations using Alembic.
    
    This function:
    1. Checks the current database revision
    2. Determines if there are any pending migrations
    3. Applies any pending migrations
    
    Returns:
        dict: A dictionary with information about the applied migrations
    """
    try:
        # Get the current database revision
        current_revision = get_current_revision()
        logger.info(f"Current database revision: {current_revision}")
        
        # Get the Alembic configuration
        alembic_cfg = Config(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "alembic.ini"))
        script = ScriptDirectory.from_config(alembic_cfg)
        
        # Get the head revision
        head_revision = script.get_current_head()
        
        # Check if we're already at the latest revision
        if current_revision == head_revision:
            logger.info("Database is already at the latest revision")
            return {
                "message": "Database is already at the latest revision",
                "current_revision": current_revision,
                "applied_migrations": []
            }
        
        # Get the migration history before applying migrations
        history_before = get_migration_history()
        
        # Apply any pending migrations
        logger.info("Applying pending migrations...")
        upgrade_database("head")
        
        # Get the migration history after applying migrations
        history_after = get_migration_history()
        
        # Determine which migrations were applied
        applied_migrations = []
        if len(history_after) > len(history_before):
            applied_migrations = history_after[:len(history_after) - len(history_before)]
        
        # Get the new current revision
        new_current_revision = get_current_revision()
        
        logger.info(f"Applied migrations. New revision: {new_current_revision}")
        return {
            "message": "Applied pending migrations",
            "previous_revision": current_revision,
            "current_revision": new_current_revision,
            "applied_migrations": applied_migrations
        }
    except SQLAlchemyError as e:
        logger.error(f"Error applying database migrations: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error applying database migrations: {e}")
        raise