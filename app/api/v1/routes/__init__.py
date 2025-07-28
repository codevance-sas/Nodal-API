from fastapi import APIRouter

# Import all the individual routers
from . import auth, core, gas_pipeline, hydraulics, ipr, operators, pipeline, pvt, surveys, users, wells

# Public router (for authentication)
auth_router = APIRouter()
auth_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Protected router (for all other API endpoints)
protected_api_router = APIRouter()
protected_api_router.include_router(core.router, prefix="/core", tags=["core"])
protected_api_router.include_router(gas_pipeline.router, prefix="/gas_pipeline", tags=["gas_pipeline"])
protected_api_router.include_router(hydraulics.router, prefix="/hydraulics", tags=["hydraulics"])
protected_api_router.include_router(ipr.router, prefix="/ipr", tags=["ipr"])
protected_api_router.include_router(operators.router, prefix="/operators", tags=["operators"])
protected_api_router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
protected_api_router.include_router(pvt.router, prefix="/pvt", tags=["pvt"])
protected_api_router.include_router(surveys.router, prefix="/surveys", tags=["surveys"])
protected_api_router.include_router(users.router, prefix="/users", tags=["users"])
protected_api_router.include_router(wells.router, prefix="/wells", tags=["wells"])



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