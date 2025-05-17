# backend/app/api/v1/routes/__init__.py
from fastapi import APIRouter

router = APIRouter()

# Import routes to include them in the router
from app.api.v1.routes.hydraulics import router as hydraulics_router
from app.api.v1.routes.pvt import router as pvt_router

# Include routers
router.include_router(hydraulics_router, prefix="/hydraulics")
router.include_router(pvt_router, prefix="/pvt")


# backend/app/schemas/__init__.py
# Empty file, just to mark as a package


# backend/app/services/hydraulics/__init__.py
# Export main functions to simplify imports
from app.services.hydraulics.engine import (
    calculate_hydraulics,
    compare_methods,
    recommend_method
)


# backend/app/services/hydraulics/correlations/__init__.py
# Export correlation functions to simplify imports
from app.services.hydraulics.correlations.hagedorn_brown import calculate_hagedorn_brown
from app.services.hydraulics.correlations.beggs_brill import calculate_beggs_brill
from app.services.hydraulics.correlations.duns_ross import calculate_duns_ross
from app.services.hydraulics.correlations.chokshi import calculate_chokshi
from app.services.hydraulics.correlations.orkiszewski import calculate_orkiszewski
from app.services.hydraulics.correlations.gray import calculate_gray
from app.services.hydraulics.correlations.mukherjee_brill import calculate_mukherjee_brill
from app.services.hydraulics.correlations.aziz import calculate_aziz
from app.services.hydraulics.correlations.hasan_kabir import calculate_hasan_kabir
from app.services.hydraulics.correlations.ansari import calculate_ansari

__all__ = [
    'calculate_hagedorn_brown',
    'calculate_beggs_brill',
    'calculate_duns_ross',
    'calculate_chokshi',
    'calculate_orkiszewski',
    'calculate_gray',
    'calculate_mukherjee_brill',
    'calculate_aziz',
    'calculate_hasan_kabir',
    'calculate_ansari'
]


# backend/app/services/pvt/__init__.py
# Export main functions to simplify imports
from app.services.pvt.engine import (
    validate_input,
    generate_pressure_range,
    calculate_pvt,
    get_pvt_at_pressure
)


# backend/utils/__init__.py
# Empty file, just to mark as a package