from fastapi import APIRouter, HTTPException, status

from app.api.models.config import RuntimeConfigResponse, RuntimeConfigUpdateRequest
from app.services.runtime_config_service import (
    RuntimeConfigError,
    read_runtime_config,
    update_runtime_config,
)

router = APIRouter(prefix="/config", tags=["config"])


@router.get(
    "/runtime",
    response_model=RuntimeConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Read local runtime configuration",
    description=(
        "Return product-safe local runtime configuration status. Secrets are masked and "
        "raw API keys are never returned."
    ),
)
async def read_runtime_configuration() -> RuntimeConfigResponse:
    return read_runtime_config()


@router.put(
    "/runtime",
    response_model=RuntimeConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update local runtime configuration",
    description=(
        "Update backend/.env for local development. Empty API key values keep the "
        "existing secret instead of clearing it."
    ),
)
async def update_runtime_configuration(
    payload: RuntimeConfigUpdateRequest,
) -> RuntimeConfigResponse:
    try:
        return update_runtime_config(payload)
    except RuntimeConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "runtime_config_error", "detail": str(exc)},
        ) from exc
