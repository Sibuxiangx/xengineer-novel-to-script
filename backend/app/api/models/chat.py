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


class ChatRunResponse(BaseModel):
    id: str = Field(..., description="Stable agent run identifier.")
    session_id: str = Field(..., description="Chat session identifier.")
    status: Literal[
        "running",
        "waiting_confirmation",
        "completed",
        "completed_with_errors",
        "failed",
    ] = Field(..., description="Run lifecycle status.")
    user_message_id: str | None = Field(
        default=None,
        description="User message that triggered this run.",
    )
    assistant_message_id: str | None = Field(
        default=None,
        description="Assistant message produced by this run, if any.",
    )
    error_message: str | None = Field(default=None, description="Run error message.")
    created_at: datetime = Field(..., description="Run creation time.")
    updated_at: datetime = Field(..., description="Run update time.")


class ChapterSplitConfirmationPayload(BaseModel):
    file_name: str = Field(..., description="Original TXT file name.")
    source_text_path: str = Field(..., description="Local source TXT artifact path.")
    text_length: int = Field(..., description="Source text length in characters.")
    adaptation_requirements: str | None = Field(
        default=None,
        description=(
            "User's first-turn adaptation requirements submitted together with the source TXT."
        ),
    )
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


class ChatTimelineItemResponse(BaseModel):
    id: str = Field(..., description="Stable timeline item identifier.")
    kind: Literal["message", "tool_call", "confirmation"] = Field(
        ...,
        description="Timeline item kind used by the chat UI.",
    )
    session_id: str = Field(..., description="Chat session identifier.")
    run_id: str | None = Field(
        default=None,
        description="Agent run identifier, when this item belongs to a run.",
    )
    message: ChatMessageResponse | None = Field(
        default=None,
        description="Message payload when kind is message.",
    )
    tool_call: ChatToolCallResponse | None = Field(
        default=None,
        description="Tool-call payload when kind is tool_call.",
    )
    confirmation: ChatConfirmationResponse | None = Field(
        default=None,
        description="Confirmation payload when kind is confirmation.",
    )
    created_at: datetime = Field(..., description="Timeline ordering timestamp.")


class ModelUsageResponse(BaseModel):
    id: str = Field(..., description="Stable UI identifier for this usage estimate.")
    project_id: str = Field(..., description="Project associated with the model call.")
    task: str = Field(..., description="Agent task name, such as generate_script_yaml.")
    provider: str = Field(..., description="Model provider name.")
    model: str = Field(..., description="Model name used for this task.")
    estimated_input_tokens: int = Field(..., description="Estimated prompt/input token count.")
    context_budget_tokens: int = Field(..., description="Context packing budget for the task.")
    included_block_ids: list[str] = Field(
        default_factory=list,
        description="Context block IDs included in the model prompt.",
    )
    omitted_block_ids: list[str] = Field(
        default_factory=list,
        description="Context block IDs omitted by context packing.",
    )
    created_at: datetime = Field(..., description="Usage estimate creation time.")


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionResponse = Field(..., description="Chat session metadata.")
    messages: list[ChatMessageResponse] = Field(..., description="Messages in display order.")
    pending_confirmations: list[ChatConfirmationResponse] = Field(
        ...,
        description="Pending confirmations requiring user action.",
    )
    tool_calls: list[ChatToolCallResponse] = Field(
        default_factory=list,
        description=(
            "All tool calls executed in this session, in chronological order. "
            "Allows the UI to render the full agent trace after a page refresh."
        ),
    )
    runs: list[ChatRunResponse] = Field(
        default_factory=list,
        description=(
            "Agent runs in chronological order, including the user and assistant "
            "message IDs used to place tool traces in the chat timeline."
        ),
    )
    timeline: list[ChatTimelineItemResponse] = Field(
        default_factory=list,
        description=(
            "Canonical chat display timeline. The UI should render this first so "
            "messages, tool calls, and confirmations keep the same order after refresh."
        ),
    )
    latest_versions: list[ScriptVersionResponse] = Field(
        default_factory=list,
        description="Latest screenplay versions for the linked project, including rejected drafts.",
    )
    model_usage: list[ModelUsageResponse] = Field(
        default_factory=list,
        description=(
            "Persisted or reconstructed model usage estimates for this chat session. "
            "The frontend uses this to restore the status-bar token counter after refresh."
        ),
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

    @property
    def adaptation_requirements(self) -> str | None:
        """Treat the first message sent with TXT as initial adaptation requirements."""

        if not self.source_text:
            return None
        content = self.message.strip()
        if not content:
            return None
        generic_messages = {
            "上传小说。",
            "我上传了一篇小说，请开始改编。",
            "请开始改编这篇小说。",
            "开始改编。",
        }
        return None if content in generic_messages else content


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
