from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.screenplay_agent import (
    AgentConfigurationError,
    AgentExecutionError,
    ScreenplayAgent,
)
from app.api.models.chat import (
    ChatConfirmationActionRequest,
    ChatRunStreamRequest,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatSseEvent,
)
from app.api.models.common import ApiErrorResponse
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.chat_agent_service import (
    ChatAgentService,
    ChatSessionNotFoundError,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_agent(settings: Annotated[Settings, Depends(get_settings)]) -> ScreenplayAgent:
    return ScreenplayAgent(settings)


def get_chat_agent_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agent: Annotated[ScreenplayAgent, Depends(get_chat_agent)],
) -> ChatAgentService:
    return ChatAgentService(session=session, settings=settings, agent=agent)


def _session_not_found(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "chat_session_not_found", "detail": "Chat session not found."},
    )


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chat session",
    description="Create an agentic chat session used by the novel-to-script workspace.",
)
async def create_chat_session(
    request: ChatSessionCreateRequest,
    service: Annotated[ChatAgentService, Depends(get_chat_agent_service)],
) -> ChatSessionResponse:
    return await service.create_session(request)


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List chat sessions",
    description="List chat sessions for the project sidebar.",
)
async def list_chat_sessions(
    service: Annotated[ChatAgentService, Depends(get_chat_agent_service)],
) -> list[ChatSessionResponse]:
    return await service.list_sessions()


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chat session detail",
    description="Return session metadata, messages, pending confirmations, and recent versions.",
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def get_chat_session_detail(
    session_id: Annotated[str, Path(description="Stable chat session identifier.")],
    service: Annotated[ChatAgentService, Depends(get_chat_agent_service)],
) -> ChatSessionDetailResponse:
    try:
        return await service.get_session_detail(session_id)
    except ChatSessionNotFoundError as exc:
        raise _session_not_found(exc) from exc


@router.post(
    "/sessions/{session_id}/runs/stream",
    status_code=status.HTTP_200_OK,
    summary="Stream an agent chat run",
    description=(
        "Send a user message and stream assistant deltas, tool calls, asset updates, "
        "and confirmation requests as Server-Sent Events."
    ),
    responses={
        status.HTTP_200_OK: {
            "model": ChatSseEvent,
            "description": "Server-Sent Event stream.",
        },
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiErrorResponse},
    },
)
async def stream_chat_run(
    session_id: Annotated[str, Path(description="Stable chat session identifier.")],
    request: ChatRunStreamRequest,
    service: Annotated[ChatAgentService, Depends(get_chat_agent_service)],
) -> StreamingResponse:
    try:
        await service.get_session_detail(session_id)
    except ChatSessionNotFoundError as exc:
        raise _session_not_found(exc) from exc
    except AgentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "agent_configuration_error", "detail": str(exc)},
        ) from exc
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "agent_execution_error", "detail": str(exc)},
        ) from exc

    return StreamingResponse(
        service.stream_user_message(session_id, request),
        media_type="text/event-stream",
    )


@router.post(
    "/sessions/{session_id}/confirmations/{confirmation_id}/stream",
    status_code=status.HTTP_200_OK,
    summary="Stream a confirmation action",
    description=(
        "Confirm or cancel a pending tool result and stream the follow-up tool calls. "
        "Chapter-split confirmation continues into import, book index generation, "
        "script generation, validation, and version save."
    ),
    responses={
        status.HTTP_200_OK: {
            "model": ChatSseEvent,
            "description": "Server-Sent Event stream.",
        },
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ApiErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiErrorResponse},
    },
)
async def stream_chat_confirmation_action(
    session_id: Annotated[str, Path(description="Stable chat session identifier.")],
    confirmation_id: Annotated[str, Path(description="Stable confirmation identifier.")],
    request: ChatConfirmationActionRequest,
    service: Annotated[ChatAgentService, Depends(get_chat_agent_service)],
) -> StreamingResponse:
    try:
        await service.get_session_detail(session_id)
    except ChatSessionNotFoundError as exc:
        raise _session_not_found(exc) from exc
    except AgentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "agent_configuration_error", "detail": str(exc)},
        ) from exc
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "agent_execution_error", "detail": str(exc)},
        ) from exc

    return StreamingResponse(
        service.stream_confirmation_action(session_id, confirmation_id, request),
        media_type="text/event-stream",
    )
