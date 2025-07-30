"""
Command-line interface for database migrations.

This module provides CLI commands for working with database migrations.

Usage:
    # Generate a new migration
    python -m app.db.cli generate "Add user table"
    
    # Apply all pending migrations
    python -m app.db.cli upgrade
    
    # Apply migrations up to a specific revision
    python -m app.db.cli upgrade abc123
    
    # Downgrade to a previous revision
    python -m app.db.cli downgrade abc123
    
    # Show migration history
    python -m app.db.cli history
    
    # Show current revision
    python -m app.db.cli current
"""
import argparse
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
from app.db.alembic_helpers import (
    generate_migration,
    upgrade_database,
    downgrade_database,
    get_current_revision,
    get_migration_history,
)

def generate_command(args):
    """Generate a new migration script."""
    try:
        logger.info(f"Generating migration: {args.message}")
        migration_path = generate_migration(args.message)
        logger.info(f"Migration script generated: {migration_path}")
        return 0
    except Exception as e:
        logger.error(f"Error generating migration: {e}")
        return 1

def upgrade_command(args):
    """Upgrade the database to the specified revision."""
    try:
        revision = args.revision or "head"
        logger.info(f"Upgrading database to revision: {revision}")
        upgrade_database(revision)
        current = get_current_revision()
        logger.info(f"Database upgraded. Current revision: {current}")
        return 0
    except Exception as e:
        logger.error(f"Error upgrading database: {e}")
        return 1

def downgrade_command(args):
    """Downgrade the database to the specified revision."""
    try:
        if not args.revision:
            logger.error("Revision is required for downgrade")
            return 1
        
        logger.info(f"Downgrading database to revision: {args.revision}")
        downgrade_database(args.revision)
        current = get_current_revision()
        logger.info(f"Database downgraded. Current revision: {current}")
        return 0
    except Exception as e:
        logger.error(f"Error downgrading database: {e}")
        return 1

def history_command(args):
    """Show migration history."""
    try:
        logger.info("Getting migration history...")
        history = get_migration_history()
        
        if not history:
            logger.info("No migrations found")
            return 0
        
        logger.info("Migration history:")
        for entry in history:
            print(entry)
        
        return 0
    except Exception as e:
        logger.error(f"Error getting migration history: {e}")
        return 1

def current_command(args):
    """Show current revision."""
    try:
        current = get_current_revision()
        logger.info(f"Current database revision: {current}")
        return 0
    except Exception as e:
        logger.error(f"Error getting current revision: {e}")
        return 1

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Database migration commands")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate a new migration")
    generate_parser.add_argument("message", help="Migration message")
    generate_parser.set_defaults(func=generate_command)
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade the database")
    upgrade_parser.add_argument("revision", nargs="?", help="Revision to upgrade to (default: head)")
    upgrade_parser.set_defaults(func=upgrade_command)
    
    # Downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade the database")
    downgrade_parser.add_argument("revision", help="Revision to downgrade to")
    downgrade_parser.set_defaults(func=downgrade_command)
    
    # History command
    history_parser = subparsers.add_parser("history", help="Show migration history")
    history_parser.set_defaults(func=history_command)
    
    # Current command
    current_parser = subparsers.add_parser("current", help="Show current revision")
    current_parser.set_defaults(func=current_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())