from pathlib import Path

from app.core.config import Settings


def test_settings_splits_cors_origins() -> None:
    settings = Settings(backend_cors_origins="http://localhost:5173, http://localhost:3000")
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]


def test_settings_resolves_sqlite_path() -> None:
    settings = Settings(sqlite_database_url="sqlite+aiosqlite:///./data/app.db")
    assert settings.sqlite_database_path == Path("data/app.db")

