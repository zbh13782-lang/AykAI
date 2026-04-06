from fastapi import APIRouter

from api.dependencies import get_services
from api.schemas.response import HealthResponse

router = APIRouter()

@router.get("/health",response_model=HealthResponse)
def health() -> HealthResponse:
    services = get_services()
    return HealthResponse(
        status="ok",
        app=services["settings"].app_name,
    )