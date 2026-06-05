from pathlib import Path
from typing import TypeVar

from pydantic import SecretStr
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import Settings
from app.schemas.book_index import BookIndex
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

    def load_prompt(self, prompt_name: str) -> str:
        prompt_path = PROMPT_DIR / prompt_name
        return prompt_path.read_text(encoding="utf-8")

    async def build_book_index(self, prompt: str) -> BookIndex:
        return await self._run_structured(
            prompt=prompt,
            output_type=BookIndex,
            task_prompt_name="build_book_index.zh.md",
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
        api_key = self._require_api_key(self.settings.deepseek_api_key)
        provider = OpenAIProvider(
            base_url=self.settings.deepseek_base_url,
            api_key=api_key,
        )
        model = OpenAIChatModel(self.settings.deepseek_model, provider=provider)
        agent = Agent(
            model=model,
            output_type=output_type,
            system_prompt=self.load_prompt("system.zh.md"),
            instructions=self.load_prompt(task_prompt_name),
            retries=2,
        )
        try:
            result = await agent.run(prompt)
        except Exception as exc:  # pragma: no cover - provider failure path
            raise AgentExecutionError(str(exc)) from exc
        return result.output

    def _require_api_key(self, value: SecretStr | None) -> str:
        if value is None or not value.get_secret_value().strip():
            raise AgentConfigurationError("Missing DEEPSEEK_API_KEY.")
        return value.get_secret_value()
