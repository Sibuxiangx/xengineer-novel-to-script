from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(..., description="Current service health status.")
    app_name: str = Field(..., description="Human-readable application name.")
    environment: str = Field(..., description="Current runtime environment.")
    docs_url: str = Field(..., description="Relative URL for the FastAPI documentation page.")

