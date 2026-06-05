import json
from datetime import UTC, datetime

from app.agent_runtime.events import format_sse_event


def test_format_sse_event_keeps_json_payload_and_non_ascii_text() -> None:
    frame = format_sse_event(
        "message.delta",
        {
            "content": "已收到小说文本",
            "created_at": datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
        },
    )

    assert frame.startswith("event: message.delta\n")
    assert frame.endswith("\n\n")

    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload == {
        "content": "已收到小说文本",
        "created_at": "2026-06-05T12:00:00+00:00",
    }
