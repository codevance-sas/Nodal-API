from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi import Depends
from app.api.v1.routes import auth_router, protected_api_router
from app.api.v1.routes.auth import get_current_user
from app.core.config import settings

app = FastAPI(
    title="Nodal API",
    description="API for Nodal Analysis",
    version="1.0.0",
    root_path="/api"
)

# Add session middleware for Google Auth
# IMPORTANT: This must be placed before the routers that use it.
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# CORS middleware
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "https://nodal-app.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the public authentication router
app.include_router(auth_router)

# Include the protected API router with a global security dependency
app.include_router(
    protected_api_router,
    dependencies=[Depends(get_current_user)]
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Nodal API"}
