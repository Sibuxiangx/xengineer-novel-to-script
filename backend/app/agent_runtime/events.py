from __future__ import annotations

import json
from typing import Any

from fastapi.encoders import jsonable_encoder


def format_sse_event(name: str, data: dict[str, Any]) -> str:
    """Encode one Server-Sent Events frame with a JSON payload."""

    encoded = json.dumps(jsonable_encoder(data), ensure_ascii=False)
    return f"event: {name}\ndata: {encoded}\n\n"
