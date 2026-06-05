from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import SecretStr
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.deepseek import DeepSeekProvider

from app.agents.deps import AgentDeps
from app.core.config import Settings
from app.schemas.book_index import BookIndex
from app.schemas.chapter_split import ChapterSplitReview, ChapterSplitRule
from app.schemas.chat import ProjectTitleSuggestion
from app.schemas.screenplay import ScreenplayYaml
from app.schemas.yaml_patch import YamlPatchPlan

PROMPT_DIR = Path(__file__).parent / "prompts"
OutputT = TypeVar("OutputT")


class AgentConfigurationError(Exception):
    """Raised when model configuration is missing."""


class AgentExecutionError(Exception):
    """Raised when the configured model provider fails."""


class ScreenplayAgent:
    """Pydantic AI boundary for DeepSeek-powered screenplay workflows."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._deps = AgentDeps(settings=settings)
        self._prompt_cache: dict[str, str] = {}
        self._model: OpenAIChatModel | None = None
        self._agent: Agent[AgentDeps, Any] | None = None
        self._model_settings: OpenAIChatModelSettings = {
            "extra_body": {"thinking": {"type": "enabled"}},
            "openai_reasoning_effort": "high",
        }

    def load_prompt(self, prompt_name: str) -> str:
        cached = self._prompt_cache.get(prompt_name)
        if cached is not None:
            return cached
        prompt_path = PROMPT_DIR / prompt_name
        prompt = prompt_path.read_text(encoding="utf-8")
        self._prompt_cache[prompt_name] = prompt
        return prompt

    async def build_book_index(self, prompt: str) -> BookIndex:
        return await self._run_structured(
            prompt=prompt,
            output_type=BookIndex,
            task_prompt_name="build_book_index.zh.md",
        )

    async def infer_project_title(self, prompt: str) -> ProjectTitleSuggestion:
        return await self._run_structured(
            prompt=prompt,
            output_type=ProjectTitleSuggestion,
            task_prompt_name="infer_project_title.zh.md",
        )

    async def infer_chapter_split_rule(self, prompt: str) -> ChapterSplitRule:
        return await self._run_structured(
            prompt=prompt,
            output_type=ChapterSplitRule,
            task_prompt_name="infer_chapter_split_rule.zh.md",
        )

    async def review_chapter_split_result(self, prompt: str) -> ChapterSplitReview:
        return await self._run_structured(
            prompt=prompt,
            output_type=ChapterSplitReview,
            task_prompt_name="review_chapter_split_result.zh.md",
        )

    async def revise_chapter_split_rule(self, prompt: str) -> ChapterSplitRule:
        return await self._run_structured(
            prompt=prompt,
            output_type=ChapterSplitRule,
            task_prompt_name="revise_chapter_split_rule.zh.md",
        )

    async def generate_script(self, prompt: str) -> ScreenplayYaml:
        return await self._run_structured(
            prompt=prompt,
            output_type=ScreenplayYaml,
            task_prompt_name="generate_script_yaml.zh.md",
        )

    async def plan_yaml_edit(self, prompt: str) -> YamlPatchPlan:
        return await self._run_structured(
            prompt=prompt,
            output_type=YamlPatchPlan,
            task_prompt_name="generate_yaml_patch.zh.md",
        )

    async def repair_script(self, prompt: str) -> ScreenplayYaml:
        return await self._run_structured(
            prompt=prompt,
            output_type=ScreenplayYaml,
            task_prompt_name="repair_from_harness.zh.md",
        )

    async def _run_structured(
        self,
        prompt: str,
        output_type: type[OutputT],
        task_prompt_name: str,
    ) -> OutputT:
        try:
            result = await self._get_agent().run(
                prompt,
                output_type=output_type,
                instructions=self.load_prompt(task_prompt_name),
                deps=self._deps,
            )
        except AgentConfigurationError:
            raise
        except Exception as exc:  # pragma: no cover - provider failure path
            raise AgentExecutionError(str(exc)) from exc
        return cast(OutputT, result.output)

    def _get_agent(self) -> Agent[AgentDeps, Any]:
        if self._agent is None:
            self._agent = Agent(
                model=self._get_model(),
                deps_type=AgentDeps,
                system_prompt=self.load_prompt("system.zh.md"),
                model_settings=self._model_settings,
                retries=2,
            )
        return self._agent

    def _get_model(self) -> OpenAIChatModel:
        if self._model is None:
            api_key = self._require_api_key(self.settings.deepseek_api_key)
            provider = DeepSeekProvider(api_key=api_key)
            self._model = OpenAIChatModel(self.settings.deepseek_model, provider=provider)
        return self._model

    def _require_api_key(self, value: SecretStr | None) -> str:
        if value is None or not value.get_secret_value().strip():
            raise AgentConfigurationError("Missing DEEPSEEK_API_KEY.")
        return value.get_secret_value()
