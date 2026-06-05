from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import screenplay_agent as screenplay_agent_module
from app.agents.deps import AgentDeps
from app.agents.screenplay_agent import ScreenplayAgent
from app.api.routes import chat as chat_routes
from app.core.config import Settings
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
