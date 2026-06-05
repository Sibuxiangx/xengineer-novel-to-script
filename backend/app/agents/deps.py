from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings


@dataclass(slots=True)
class AgentDeps:
    """Runtime dependencies exposed to Pydantic AI tools through RunContext."""

    settings: Settings
    session_id: str | None = None
    project_id: str | None = None
    toolbox: Any | None = None
