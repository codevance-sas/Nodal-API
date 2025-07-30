from datetime import datetime, timezone
from typing import Optional

def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensures a datetime object is timezone-aware by adding UTC timezone if it's naive.
    
    Args:
        dt: A datetime object that may or may not have timezone information
        
    Returns:
        A timezone-aware datetime object with UTC timezone, or None if input is None
    """
    if dt is None:
        return None
        
    # If the datetime is already timezone-aware, return it as is
    if dt.tzinfo is not None:
        return dt
        
    # Otherwise, make it timezone-aware with UTC
    return dt.replace(tzinfo=timezone.utc)