from fastapi import APIRouter

router = APIRouter(tags=["core"])

@router.get("/health")
def health_check():
    return {"status": "ok"}
