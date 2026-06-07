from pathlib import Path

from app.api.models.config import RuntimeConfigResponse, RuntimeConfigUpdateRequest
from app.core.config import BACKEND_ROOT, ENV_FILE_PATH, Settings, get_settings

ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class RuntimeConfigError(RuntimeError):
    """Raised when local runtime configuration cannot be read or written."""


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if (
        len(stripped) >= 2
        and ((stripped[0] == stripped[-1] == '"') or (stripped[0] == stripped[-1] == "'"))
    ):
        return stripped[1:-1]
    return stripped


def _parse_env(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = _strip_quotes(value)
    return values


def _format_env_value(value: str) -> str:
    if value and all(char.isalnum() or char in "_.:/@+-" for char in value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _set_env_value(content: str, key: str, value: str) -> str:
    next_line = f"{key}={_format_env_value(value)}"
    lines = content.splitlines()
    for index, raw_line in enumerate(lines):
        stripped = raw_line.lstrip()
        if stripped.startswith("#") or "=" not in raw_line:
            continue
        current_key = raw_line.split("=", 1)[0].strip()
        if current_key == key:
            lines[index] = next_line
            return "\n".join(lines) + "\n"
    prefix = "\n" if content and not content.endswith("\n") else ""
    return f"{content}{prefix}{next_line}\n"


def _ensure_env_file(env_file_path: Path = ENV_FILE_PATH) -> None:
    if env_file_path.exists():
        return
    if not ENV_EXAMPLE_PATH.exists():
        raise RuntimeConfigError("backend/.env.example 不存在，无法创建本地配置文件。")
    env_file_path.parent.mkdir(parents=True, exist_ok=True)
    env_file_path.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def _load_settings(env_file_path: Path = ENV_FILE_PATH) -> Settings:
    return Settings(_env_file=env_file_path)  # pyright: ignore[reportCallIssue]


def _display_env_path(env_file_path: Path) -> str:
    try:
        return str(env_file_path.relative_to(BACKEND_ROOT))
    except ValueError:
        return str(env_file_path)


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return value[0] + "***" + value[-1]
    return f"{value[:5]}...{value[-4:]}"


def read_runtime_config(env_file_path: Path = ENV_FILE_PATH) -> RuntimeConfigResponse:
    settings = _load_settings(env_file_path)
    secret = settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else None
    return RuntimeConfigResponse(
        env_file_exists=env_file_path.exists(),
        env_file_path=_display_env_path(env_file_path),
        deepseek_api_key_configured=bool(secret),
        deepseek_api_key_masked=_mask_secret(secret),
        deepseek_base_url=settings.deepseek_base_url,
        deepseek_model=settings.deepseek_model,
        deepseek_fast_model=settings.deepseek_fast_model,
        model_context_limit=settings.model_context_limit,
    )


def update_runtime_config(
    payload: RuntimeConfigUpdateRequest,
    env_file_path: Path = ENV_FILE_PATH,
) -> RuntimeConfigResponse:
    _ensure_env_file(env_file_path)
    content = env_file_path.read_text(encoding="utf-8")
    updates: dict[str, str] = {}

    if payload.deepseek_api_key is not None and payload.deepseek_api_key.strip():
        updates["DEEPSEEK_API_KEY"] = payload.deepseek_api_key.strip()
    if payload.deepseek_base_url is not None:
        updates["DEEPSEEK_BASE_URL"] = payload.deepseek_base_url.strip()
    if payload.deepseek_model is not None:
        updates["DEEPSEEK_MODEL"] = payload.deepseek_model.strip()
    if payload.deepseek_fast_model is not None:
        updates["DEEPSEEK_FAST_MODEL"] = payload.deepseek_fast_model.strip()
    if payload.model_context_limit is not None:
        updates["MODEL_CONTEXT_LIMIT"] = str(payload.model_context_limit)

    for key, value in updates.items():
        if not value:
            continue
        content = _set_env_value(content, key, value)

    env_file_path.write_text(content, encoding="utf-8")
    get_settings.cache_clear()
    return read_runtime_config(env_file_path)
