from fastapi import APIRouter, Depends, HTTPException, status
from app.api.v1.dependencies.auth import get_admin_user
from app.db.migrations import create_db_and_tables

router = APIRouter(tags=["core"])

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.post("/apply-migrations", status_code=status.HTTP_200_OK)
def apply_migrations(admin_user=Depends(get_admin_user)):
    """
    Apply pending database migrations using Alembic.
    
    This endpoint:
    1. Checks the current database revision
    2. Determines if there are any pending migrations
    3. Applies any pending migrations
    
    Returns:
        dict: A dictionary with information about the applied migrations, including:
            - message: A message describing the result
            - previous_revision: The revision before applying migrations
            - current_revision: The revision after applying migrations
            - applied_migrations: A list of migrations that were applied
    
    Note:
        This endpoint requires admin privileges.
    """
    try:
        result = create_db_and_tables()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying database migrations: {str(e)}"
        )
