from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agent_runtime.chat_toolbox import (
    ChapterSplitProposedToolResult,
    ConfirmationRequestedToolResult,
    ProjectCreatedToolResult,
)
from app.agents import screenplay_agent as screenplay_agent_module
from app.agents.deps import AgentDeps
from app.agents.screenplay_agent import ScreenplayAgent
from app.api.models.projects import ChapterSplitInferencePreview
from app.api.routes import chat as chat_routes
from app.core.config import Settings
from app.schemas.chapter_split import ChapterSplitRule
from app.schemas.chat import ProjectTitleSuggestion


def make_settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_env": "local",
        "app_name": "XEngineer Novel-to-Script Backend",
        "deepseek_api_key": "sk-test",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_model": "deepseek-v4-pro",
        "model_context_limit": 1_000_000,
        "backend_cors_origins": "http://localhost:5173",
        "sqlite_database_url": "sqlite+aiosqlite:///./data/app.db",
        "local_artifact_root": Path("./data/projects"),
        "database_echo": False,
    }
    data.update(overrides)
    return Settings.model_validate(data)


def test_chat_agent_dependency_reuses_process_singleton() -> None:
    chat_routes.get_process_screenplay_agent.cache_clear()
    try:
        first = chat_routes.get_chat_agent()
        second = chat_routes.get_chat_agent()
        assert first is second
    finally:
        chat_routes.get_process_screenplay_agent.cache_clear()


@pytest.mark.asyncio
async def test_screenplay_agent_reuses_model_and_base_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = {"provider": 0, "model": 0, "agent": 0}
    run_calls: list[dict[str, Any]] = []

    class FakeProvider:
        def __init__(self, *, api_key: str) -> None:
            created["provider"] += 1
            assert api_key == "sk-test"

    class FakeModel:
        def __init__(self, model_name: str, *, provider: FakeProvider) -> None:
            created["model"] += 1
            assert model_name == "deepseek-v4-pro"
            assert isinstance(provider, FakeProvider)

    class FakeAgent:
        def __init__(
            self,
            *,
            model: FakeModel,
            deps_type: type[AgentDeps],
            system_prompt: str,
            model_settings: dict[str, Any],
            retries: int,
        ) -> None:
            created["agent"] += 1
            assert isinstance(model, FakeModel)
            assert deps_type is AgentDeps
            assert "AI 剧本改编助手" in system_prompt
            assert model_settings["extra_body"]["thinking"]["type"] == "enabled"
            assert retries == 2

        async def run(
            self,
            prompt: str,
            *,
            output_type: type[ProjectTitleSuggestion],
            instructions: str,
            deps: AgentDeps,
        ) -> SimpleNamespace:
            run_calls.append(
                {
                    "prompt": prompt,
                    "output_type": output_type,
                    "instructions": instructions,
                    "deps": deps,
                }
            )
            assert output_type is ProjectTitleSuggestion
            return SimpleNamespace(
                output=ProjectTitleSuggestion(
                    title="复用测试",
                    reason="fake agent 只用于验证运行时复用。",
                )
            )

    monkeypatch.setattr(screenplay_agent_module, "DeepSeekProvider", FakeProvider)
    monkeypatch.setattr(screenplay_agent_module, "OpenAIChatModel", FakeModel)
    monkeypatch.setattr(screenplay_agent_module, "Agent", FakeAgent)

    agent = ScreenplayAgent(make_settings())
    first = await agent.infer_project_title("第一次调用")
    second = await agent.infer_project_title("第二次调用")

    assert first.title == "复用测试"
    assert second.title == "复用测试"
    assert created == {"provider": 1, "model": 1, "agent": 1}
    assert [call["prompt"] for call in run_calls] == ["第一次调用", "第二次调用"]
    assert all(call["deps"].settings is agent.settings for call in run_calls)
    assert all("推导一个简洁" in call["instructions"] for call in run_calls)


@pytest.mark.asyncio
async def test_source_ingestion_tool_agent_uses_pydantic_tool_calls() -> None:
    async def scripted_model(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> ModelResponse:
        returned_tools = [
            part
            for message in messages
            for part in message.parts
            if part.part_kind == "tool-return"
        ]
        assert {tool.name for tool in info.function_tools} >= {
            "propose_project_title",
            "create_project",
            "propose_chapter_split",
            "request_chapter_split_confirmation",
        }
        match len(returned_tools):
            case 0:
                return ModelResponse([ToolCallPart("propose_project_title", {})])
            case 1:
                return ModelResponse([ToolCallPart("create_project", {"title": "雾港来信改编"})])
            case 2:
                return ModelResponse([ToolCallPart("propose_chapter_split", {})])
            case 3:
                return ModelResponse([ToolCallPart("request_chapter_split_confirmation", {})])
            case _:
                return ModelResponse([TextPart("已创建分章确认。")])

    class FakeToolbox:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.project_id: str | None = None

        async def propose_project_title(self) -> ProjectTitleSuggestion:
            self.calls.append("propose_project_title")
            return ProjectTitleSuggestion(title="雾港来信改编", reason="测试标题。")

        async def create_project(self, title: str) -> ProjectCreatedToolResult:
            self.calls.append(f"create_project:{title}")
            self.project_id = "proj_test"
            return ProjectCreatedToolResult(
                project_id="proj_test",
                title=title,
                source_text_path="/tmp/source.txt",
            )

        async def propose_chapter_split(self) -> ChapterSplitProposedToolResult:
            self.calls.append("propose_chapter_split")
            return ChapterSplitProposedToolResult(
                rule=ChapterSplitRule(
                    strategy="line_regex",
                    heading_regex=r"^第.+章.*$",
                    title_source="full_line",
                    confidence=0.9,
                    reason="测试规则。",
                    examples=["第一章 雾港来信"],
                ),
                preview=ChapterSplitInferencePreview(
                    chapter_count=1,
                    titles=["第一章 雾港来信"],
                    last_titles=["第一章 雾港来信"],
                    candidate_heading_count=1,
                    unmatched_candidate_count=0,
                    unmatched_candidates=[],
                ),
                iteration_count=1,
            )

        async def request_chapter_split_confirmation(self) -> ConfirmationRequestedToolResult:
            self.calls.append("request_chapter_split_confirmation")
            return ConfirmationRequestedToolResult(
                confirmation_id="confirm_test",
                prompt="请确认当前分章预览。",
                chapter_count=1,
            )

    toolbox = FakeToolbox()
    agent = ScreenplayAgent(make_settings())
    agent._model = FunctionModel(scripted_model)  # pyright: ignore[reportPrivateUsage]

    result = await agent.run_source_ingestion_tools(
        "用户上传了小说 TXT 原文。",
        deps=AgentDeps(settings=agent.settings, toolbox=toolbox),
    )

    assert result == "已创建分章确认。"
    assert toolbox.calls == [
        "propose_project_title",
        "create_project:雾港来信改编",
        "propose_chapter_split",
        "request_chapter_split_confirmation",
    ]
