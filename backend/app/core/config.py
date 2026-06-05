from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field("local", description="Runtime environment name.")
    app_name: str = Field(
        "XEngineer Novel-to-Script Backend",
        description="Application name shown in OpenAPI and health responses.",
    )
    deepseek_api_key: SecretStr | None = Field(
        default=None,
        description="DeepSeek API key loaded from the local dotenv file.",
    )
    deepseek_base_url: str = Field(
        "https://api.deepseek.com",
        description="DeepSeek-compatible API base URL.",
    )
    deepseek_model: str = Field(
        "deepseek-v4-pro",
        description="Primary model name used by the screenplay agent.",
    )
    model_context_limit: int = Field(
        1_000_000,
        ge=1,
        description="Configured context window used by token budgeting services.",
    )
    script_repair_max_attempts: int = Field(
        3,
        ge=0,
        le=5,
        description="Maximum automatic YAML repair attempts after harness rejection.",
    )
    context_reserved_output_tokens: int = Field(
        80_000,
        ge=1,
        description="Tokens reserved for model output before input context packing.",
    )
    context_reserved_instruction_tokens: int = Field(
        20_000,
        ge=1,
        description="Tokens reserved for system and task instructions before context packing.",
    )
    context_safety_margin_ratio: float = Field(
        0.30,
        ge=0,
        lt=1,
        description="Safety margin applied to local token estimates before packing input context.",
    )
    context_source_excerpt_chars: int = Field(
        6_000,
        ge=100,
        description="Maximum source characters included per chapter excerpt block.",
    )
    backend_cors_origins: str = Field(
        "http://localhost:5173",
        description="Comma-separated list of allowed frontend origins.",
    )
    sqlite_database_url: str = Field(
        "sqlite+aiosqlite:///./data/app.db",
        description="Async SQLAlchemy database URL for local SQLite storage.",
    )
    local_artifact_root: Path = Field(
        Path("./data/projects"),
        description="Root directory for project artifacts such as chapters and YAML files.",
    )
    database_echo: bool = Field(
        False,
        description="Enable SQLAlchemy SQL logging for local debugging.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def sqlite_database_path(self) -> Path | None:
        prefix = "sqlite+aiosqlite:///"
        if not self.sqlite_database_url.startswith(prefix):
            return None
        path_value = self.sqlite_database_url.removeprefix(prefix)
        if path_value == ":memory:":
            return None
        return Path(path_value)

    def ensure_local_paths(self) -> None:
        self.local_artifact_root.mkdir(parents=True, exist_ok=True)
        database_path = self.sqlite_database_path
        if database_path is not None:
            database_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def effective_context_input_budget(self) -> int:
        reserved = self.context_reserved_output_tokens + self.context_reserved_instruction_tokens
        available = max(1, self.model_context_limit - reserved)
        return max(1, int(available * (1 - self.context_safety_margin_ratio)))


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
