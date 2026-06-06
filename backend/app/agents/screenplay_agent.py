import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import SecretStr
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
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
StreamDeltaCallback = Callable[[dict[str, Any]], Awaitable[None]]
FAST_STRUCTURED_TASK_PROMPTS = frozenset(
    {
        "build_book_index.zh.md",
        "generate_script_yaml.zh.md",
    }
)


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
        self._model: Model | None = None
        self._fast_model: Model | None = None
        self._agent: Agent[AgentDeps, Any] | None = None
        self._fast_agent: Agent[AgentDeps, Any] | None = None
        self._tool_agent: Agent[AgentDeps, str] | None = None
        self._model_settings: OpenAIChatModelSettings = {
            "extra_body": {"thinking": {"type": "enabled"}},
            "openai_reasoning_effort": "high",
        }
        self._fast_model_settings: OpenAIChatModelSettings = {
            "extra_body": {"thinking": {"type": "disabled"}},
        }

    def load_prompt(self, prompt_name: str) -> str:
        cached = self._prompt_cache.get(prompt_name)
        if cached is not None:
            return cached
        prompt_path = PROMPT_DIR / prompt_name
        prompt = prompt_path.read_text(encoding="utf-8")
        self._prompt_cache[prompt_name] = prompt
        return prompt

    async def build_book_index(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> BookIndex:
        return await self._run_structured(
            prompt=prompt,
            output_type=BookIndex,
            task_prompt_name="build_book_index.zh.md",
            stream_callback=stream_callback,
        )

    async def infer_project_title(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> ProjectTitleSuggestion:
        return await self._run_structured(
            prompt=prompt,
            output_type=ProjectTitleSuggestion,
            task_prompt_name="infer_project_title.zh.md",
            stream_callback=stream_callback,
        )

    async def infer_chapter_split_rule(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> ChapterSplitRule:
        return await self._run_structured(
            prompt=prompt,
            output_type=ChapterSplitRule,
            task_prompt_name="infer_chapter_split_rule.zh.md",
            stream_callback=stream_callback,
        )

    async def review_chapter_split_result(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> ChapterSplitReview:
        return await self._run_structured(
            prompt=prompt,
            output_type=ChapterSplitReview,
            task_prompt_name="review_chapter_split_result.zh.md",
            stream_callback=stream_callback,
        )

    async def revise_chapter_split_rule(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> ChapterSplitRule:
        return await self._run_structured(
            prompt=prompt,
            output_type=ChapterSplitRule,
            task_prompt_name="revise_chapter_split_rule.zh.md",
            stream_callback=stream_callback,
        )

    async def generate_script(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> ScreenplayYaml:
        return await self._run_structured(
            prompt=prompt,
            output_type=ScreenplayYaml,
            task_prompt_name="generate_script_yaml.zh.md",
            stream_callback=stream_callback,
        )

    async def plan_yaml_edit(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> YamlPatchPlan:
        return await self._run_structured(
            prompt=prompt,
            output_type=YamlPatchPlan,
            task_prompt_name="generate_yaml_patch.zh.md",
            stream_callback=stream_callback,
        )

    async def repair_script(
        self,
        prompt: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> ScreenplayYaml:
        return await self._run_structured(
            prompt=prompt,
            output_type=ScreenplayYaml,
            task_prompt_name="repair_from_validation.zh.md",
            stream_callback=stream_callback,
        )

    async def run_source_ingestion_tools(self, prompt: str, deps: AgentDeps) -> str:
        """Run the chat tool agent for source ingestion and chapter-split confirmation."""

        try:
            result = await self._get_tool_agent().run(
                prompt,
                deps=deps,
                instructions=self.load_prompt("chat_tool_orchestration.zh.md"),
            )
        except AgentConfigurationError:
            raise
        except AgentExecutionError:
            raise
        except Exception as exc:  # pragma: no cover - provider failure path
            raise AgentExecutionError(str(exc)) from exc
        return result.output

    async def run_chat_instruction_tools(self, prompt: str, deps: AgentDeps) -> str:
        """Run the chat tool agent for natural-language project instructions."""

        try:
            result = await self._get_tool_agent().run(
                prompt,
                deps=deps,
                instructions=self.load_prompt("chat_tool_orchestration.zh.md"),
            )
        except AgentConfigurationError:
            raise
        except Exception as exc:  # pragma: no cover - provider failure path
            raise AgentExecutionError(str(exc)) from exc
        return result.output

    async def _run_structured(
        self,
        prompt: str,
        output_type: type[OutputT],
        task_prompt_name: str,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> OutputT:
        try:
            agent = self._get_structured_agent(task_prompt_name)
            if stream_callback is None:
                result = await agent.run(
                    prompt,
                    output_type=output_type,
                    instructions=self.load_prompt(task_prompt_name),
                    deps=self._deps,
                )
                return cast(OutputT, result.output)

            output: OutputT | None = None
            async with agent.run_stream_events(
                prompt,
                output_type=output_type,
                instructions=self.load_prompt(task_prompt_name),
                deps=self._deps,
            ) as stream:
                async for event in stream:
                    delta = self._stream_delta_payload(event)
                    if delta is not None:
                        await stream_callback(
                            {
                                "task": task_prompt_name.removesuffix(".zh.md"),
                                **delta,
                            }
                        )
                    if getattr(event, "event_kind", None) == "agent_run_result":
                        result = cast(Any, event).result
                        output = cast(OutputT, result.output)
            if output is None:
                raise AgentExecutionError("Model stream finished without a final result.")
            return output
        except AgentConfigurationError:
            raise
        except AgentExecutionError:
            raise
        except Exception as exc:  # pragma: no cover - provider failure path
            raise AgentExecutionError(str(exc)) from exc

    @staticmethod
    def _stream_delta_payload(event: Any) -> dict[str, Any] | None:
        if getattr(event, "event_kind", None) != "part_delta":
            return None

        delta = getattr(event, "delta", None)
        delta_kind = getattr(delta, "part_delta_kind", "")
        content = ""

        if delta_kind == "text":
            content = getattr(delta, "content_delta", "") or ""
        elif delta_kind == "thinking":
            content = getattr(delta, "content_delta", "") or ""
        elif delta_kind == "tool_call":
            args_delta = getattr(delta, "args_delta", None)
            if isinstance(args_delta, str):
                content = args_delta
            elif args_delta is not None:
                content = json.dumps(args_delta, ensure_ascii=False)

        if not content:
            return None
        return {
            "stream_kind": delta_kind,
            "content": content,
        }

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

    def _get_fast_agent(self) -> Agent[AgentDeps, Any]:
        if self._fast_agent is None:
            self._fast_agent = Agent(
                model=self._get_fast_model(),
                deps_type=AgentDeps,
                system_prompt=self.load_prompt("system.zh.md"),
                model_settings=self._fast_model_settings,
                retries=2,
            )
        return self._fast_agent

    def _get_structured_agent(self, task_prompt_name: str) -> Agent[AgentDeps, Any]:
        if task_prompt_name in FAST_STRUCTURED_TASK_PROMPTS:
            return self._get_fast_agent()
        return self._get_agent()

    def _get_tool_agent(self) -> Agent[AgentDeps, str]:
        if self._tool_agent is None:
            agent = Agent(
                model=self._get_model(),
                output_type=str,
                deps_type=AgentDeps,
                system_prompt=self.load_prompt("system.zh.md"),
                model_settings=self._model_settings,
                retries=2,
            )
            self._register_chat_tools(agent)
            self._tool_agent = agent
        return self._tool_agent

    def _register_chat_tools(self, agent: Agent[AgentDeps, str]) -> None:
        @agent.tool(
            name="propose_project_title",
            description="根据当前上传的 TXT 文件名和正文片段，为改编项目推导中文项目名。",
        )
        async def propose_project_title(ctx: RunContext[AgentDeps]) -> dict[str, Any]:
            result = await self._require_toolbox(ctx).propose_project_title()
            return result.model_dump(mode="json")

        @agent.tool(
            name="create_project",
            description="创建改编项目，并把当前上传的 TXT 原文保存为项目资产。",
        )
        async def create_project(ctx: RunContext[AgentDeps], title: str) -> dict[str, Any]:
            result = await self._require_toolbox(ctx).create_project(title)
            ctx.deps.project_id = result.project_id
            return result.model_dump(mode="json")

        @agent.tool(
            name="propose_chapter_split",
            description="基于当前项目的 TXT 原文推导分章规则，并返回本地切分预览。",
        )
        async def propose_chapter_split(ctx: RunContext[AgentDeps]) -> dict[str, Any]:
            result = await self._require_toolbox(ctx).propose_chapter_split()
            return result.model_dump(mode="json")

        @agent.tool(
            name="request_chapter_split_confirmation",
            description="创建分章确认点，暂停当前 run，等待用户确认或手动调整分章规则。",
        )
        async def request_chapter_split_confirmation(ctx: RunContext[AgentDeps]) -> dict[str, Any]:
            result = await self._require_toolbox(ctx).request_chapter_split_confirmation()
            return result.model_dump(mode="json")

        @agent.tool(
            name="edit_script_yaml",
            description="根据用户自然语言说明，对当前项目剧本 YAML 生成并应用结构化编辑操作。",
        )
        async def edit_script_yaml(ctx: RunContext[AgentDeps], instruction: str) -> dict[str, Any]:
            toolbox = self._require_toolbox(ctx)
            project_id = ctx.deps.project_id or toolbox.project_id
            if project_id is None:
                raise RuntimeError("当前会话还没有可编辑的项目。")
            result = await toolbox.edit_script_yaml(project_id, instruction)
            return result.model_dump(mode="json")

        @agent.tool(
            name="build_book_index",
            description="为已导入章节的项目构建 book_index.json 剧情索引。",
        )
        async def build_book_index(
            ctx: RunContext[AgentDeps],
            project_id: str,
            force_rebuild: bool = True,
        ) -> dict[str, Any]:
            result = await self._require_toolbox(ctx).build_book_index(project_id, force_rebuild)
            return result.model_dump(mode="json")

        @agent.tool(
            name="generate_script_yaml",
            description="基于项目章节和 book_index.json 生成剧本 YAML，并运行本地验证。",
        )
        async def generate_script_yaml(
            ctx: RunContext[AgentDeps],
            project_id: str,
            force_regenerate: bool = True,
        ) -> dict[str, Any]:
            result = await self._require_toolbox(ctx).generate_script_yaml(
                project_id,
                force_regenerate,
            )
            return result.model_dump(mode="json")

    def _require_toolbox(self, ctx: RunContext[AgentDeps]) -> Any:
        if ctx.deps.toolbox is None:
            raise RuntimeError("Agent toolbox is not configured for this run.")
        return ctx.deps.toolbox

    def _get_model(self) -> Model:
        if self._model is None:
            api_key = self._require_api_key(self.settings.deepseek_api_key)
            provider = DeepSeekProvider(api_key=api_key)
            self._model = OpenAIChatModel(self.settings.deepseek_model, provider=provider)
        return self._model

    def _get_fast_model(self) -> Model:
        if self._fast_model is None:
            api_key = self._require_api_key(self.settings.deepseek_api_key)
            provider = DeepSeekProvider(api_key=api_key)
            self._fast_model = OpenAIChatModel(
                self.settings.deepseek_fast_model,
                provider=provider,
            )
        return self._fast_model

    def _require_api_key(self, value: SecretStr | None) -> str:
        if value is None or not value.get_secret_value().strip():
            raise AgentConfigurationError("Missing DEEPSEEK_API_KEY.")
        return value.get_secret_value()
