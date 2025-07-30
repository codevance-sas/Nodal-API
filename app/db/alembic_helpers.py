"""
Helper functions for working with Alembic migrations.
"""
import os
import sys
import logging
from pathlib import Path
import subprocess
from typing import List, Optional

# Configure logging
logger = logging.getLogger(__name__)

def run_alembic_command(command: List[str], capture_output: bool = False) -> Optional[str]:
    """
    Run an Alembic command as a subprocess.
    
    Args:
        command: List of command arguments to pass to alembic
        capture_output: Whether to capture and return the command output
        
    Returns:
        The command output if capture_output is True, otherwise None
        
    Raises:
        RuntimeError: If the command fails
    """
    # Ensure we're in the project root directory
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)
    
    # Construct the full command
    full_command = [sys.executable, "-m", "alembic"] + command
    
    try:
        logger.info(f"Running Alembic command: {' '.join(full_command)}")
        
        if capture_output:
            result = subprocess.run(
                full_command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout
        else:
            subprocess.run(full_command, check=True)
            return None
            
    except subprocess.CalledProcessError as e:
        error_message = f"Alembic command failed with exit code {e.returncode}"
        if e.stderr:
            error_message += f": {e.stderr}"
        logger.error(error_message)
        raise RuntimeError(error_message)

def generate_migration(message: str) -> str:
    """
    Generate a new migration script using Alembic's autogenerate feature.
    
    Args:
        message: The migration message/description
        
    Returns:
        The path to the generated migration script
    """
    output = run_alembic_command(["revision", "--autogenerate", "-m", message], capture_output=True)
    
    # Extract the path to the generated migration script from the output
    if output and "Generating" in output:
        for line in output.splitlines():
            if "Generating" in line and ".py" in line:
                # Extract the migration script path
                parts = line.split("Generating ")
                if len(parts) > 1:
                    return parts[1].strip()
    
    raise RuntimeError("Failed to extract migration script path from Alembic output")

def upgrade_database(revision: str = "head") -> None:
    """
    Upgrade the database to the specified revision.
    
    Args:
        revision: The revision to upgrade to (default: "head")
    """
    run_alembic_command(["upgrade", revision])

def downgrade_database(revision: str) -> None:
    """
    Downgrade the database to the specified revision.
    
    Args:
        revision: The revision to downgrade to
    """
    run_alembic_command(["downgrade", revision])

def get_current_revision() -> str:
    """
    Get the current database revision.
    
    Returns:
        The current revision identifier
    """
    output = run_alembic_command(["current"], capture_output=True)
    
    if output:
        # Extract the revision from the output
        for line in output.splitlines():
            if "current" in line.lower() and ":" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    return parts[1].strip()
    
    return "No revision found"

def get_migration_history() -> List[str]:
    """
    Get the migration history.
    
    Returns:
        A list of migration entries
    """
    output = run_alembic_command(["history"], capture_output=True)
    
    if output:
        return [line.strip() for line in output.splitlines() if line.strip()]
    
    return []