"""
Script to generate the initial Alembic migration.

This script should be run once to create the initial migration script
that represents the current state of the database schema.

Usage:
    python -m app.db.generate_initial_migration
"""
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import all models to ensure they are registered with SQLModel.metadata
import app.models

# Import the helper functions
from app.db.alembic_helpers import generate_migration

def main():
    """Generate the initial migration script."""
    try:
        logger.info("Generating initial migration script...")
        migration_path = generate_migration("Initial migration")
        logger.info(f"Initial migration script generated: {migration_path}")
        logger.info(
            "To apply this migration, run: "
            "python -m alembic upgrade head"
        )
        return 0
    except Exception as e:
        logger.error(f"Error generating initial migration: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())