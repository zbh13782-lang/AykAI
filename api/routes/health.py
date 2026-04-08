from fastapi import APIRouter

from api.schemas.response import HealthResponse
from config.settings import get_settings

router = APIRouter()

@router.get("/health",response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
    )