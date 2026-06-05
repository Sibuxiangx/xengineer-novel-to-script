from pathlib import Path
from typing import Any

from app.core.config import Settings


def make_settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_env": "local",
        "app_name": "XEngineer Novel-to-Script Backend",
        "deepseek_api_key": None,
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


def test_settings_splits_cors_origins() -> None:
    settings = make_settings(
        backend_cors_origins="http://localhost:5173, http://localhost:3000"
    )
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]


def test_settings_resolves_sqlite_path() -> None:
    settings = make_settings(sqlite_database_url="sqlite+aiosqlite:///./data/app.db")
    assert settings.sqlite_database_path == Path("data/app.db")
