from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.models.projects import ChapterSplitInferencePreview
from app.api.models.scripts import ScriptVersionResponse
from app.schemas.chapter_split import ChapterSplitRule


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(
        default=None,
        description="Optional temporary chat title before the agent infers the project title.",
    )


class ChatSessionResponse(BaseModel):
    id: str = Field(..., description="Stable chat session identifier.")
    project_id: str | None = Field(default=None, description="Linked project ID, if created.")
    title: str = Field(..., description="Sidebar display title.")
    status: Literal["active", "archived"] = Field(..., description="Chat session status.")
    pending_confirmation_count: int = Field(..., description="Open confirmations awaiting user.")
    created_at: datetime = Field(..., description="Session creation time.")
    updated_at: datetime = Field(..., description="Session last update time.")


class ChatMessageResponse(BaseModel):
    id: str = Field(..., description="Stable chat message identifier.")
    session_id: str = Field(..., description="Chat session identifier.")
    role: Literal["user", "assistant", "system", "tool"] = Field(..., description="Message role.")
    content: str = Field(..., description="Message content.")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured metadata for UI rendering.",
    )
    created_at: datetime = Field(..., description="Message creation time.")


class ChatToolCallResponse(BaseModel):
    id: str = Field(..., description="Stable tool call identifier.")
    session_id: str = Field(..., description="Chat session identifier.")
    run_id: str = Field(..., description="Agent run identifier.")
    name: str = Field(..., description="Tool name.")
    status: Literal["running", "completed", "failed"] = Field(..., description="Tool status.")
    input: dict[str, Any] | None = Field(default=None, description="Tool input summary.")
    output: dict[str, Any] | None = Field(default=None, description="Tool output summary.")
    error_message: str | None = Field(default=None, description="Tool error message.")
    duration_ms: int | None = Field(
        default=None,
        description="Tool execution duration in milliseconds, when finished.",
    )
    created_at: datetime = Field(..., description="Tool call creation time.")
    updated_at: datetime = Field(..., description="Tool call update time.")


class ChapterSplitConfirmationPayload(BaseModel):
    file_name: str = Field(..., description="Original TXT file name.")
    source_text_path: str = Field(..., description="Local source TXT artifact path.")
    text_length: int = Field(..., description="Source text length in characters.")
    rule: ChapterSplitRule = Field(..., description="Inferred chapter split rule.")
    preview: ChapterSplitInferencePreview = Field(..., description="Local split preview.")


class ChatConfirmationResponse(BaseModel):
    id: str = Field(..., description="Stable confirmation identifier.")
    session_id: str = Field(..., description="Chat session identifier.")
    project_id: str | None = Field(default=None, description="Linked project ID.")
    kind: Literal["chapter_split"] = Field(..., description="Confirmation kind.")
    status: Literal["pending", "confirmed", "cancelled"] = Field(
        ...,
        description="Confirmation status.",
    )
    prompt: str = Field(..., description="Assistant prompt shown to the user.")
    payload: ChapterSplitConfirmationPayload = Field(
        ...,
        description="Structured payload for the confirmation UI.",
    )
    created_at: datetime = Field(..., description="Confirmation creation time.")
    resolved_at: datetime | None = Field(default=None, description="Confirmation resolution time.")


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionResponse = Field(..., description="Chat session metadata.")
    messages: list[ChatMessageResponse] = Field(..., description="Messages in display order.")
    pending_confirmations: list[ChatConfirmationResponse] = Field(
        ...,
        description="Pending confirmations requiring user action.",
    )
    latest_versions: list[ScriptVersionResponse] = Field(
        default_factory=list,
        description="Latest screenplay versions for the linked project, including rejected drafts.",
    )


class ChatRunStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User natural-language message.")
    source_file_name: str | None = Field(
        default=None,
        description="TXT file name when uploading or pasting source text.",
    )
    source_text: str | None = Field(
        default=None,
        min_length=1,
        description="Optional novel TXT content. When present, the agent starts ingestion.",
    )
    screenplay_format: str = Field(
        "short_drama",
        description="Target screenplay format for newly created projects.",
    )


class ChatConfirmationActionRequest(BaseModel):
    action: Literal["confirm", "cancel"] = Field(
        ...,
        description="Confirm or cancel the pending tool result.",
    )
    message: str | None = Field(
        default=None,
        description="Optional user note shown in the chat transcript.",
    )
    chapter_split_rule: ChapterSplitRule | None = Field(
        default=None,
        description="Optional edited split rule supplied by the user before confirmation.",
    )


class ChatSseEvent(BaseModel):
    event: str = Field(..., description="SSE event name.")
    data: dict[str, Any] = Field(..., description="JSON payload for the event.")
