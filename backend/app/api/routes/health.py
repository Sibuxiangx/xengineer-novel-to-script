from fastapi import APIRouter, status

from app.api.models.health import HealthResponse
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Read service health",
    description="Return runtime health and documentation metadata for the backend service.",
)
async def read_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        docs_url="/docs",
    )

