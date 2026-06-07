from pathlib import Path

from fastapi.testclient import TestClient

from app.api.models.config import RuntimeConfigUpdateRequest
from app.core.config import get_settings
from app.main import app
from app.services.runtime_config_service import read_runtime_config, update_runtime_config


def test_runtime_config_masks_deepseek_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=sk-test-secret-value",
                "DEEPSEEK_BASE_URL=https://api.deepseek.com",
                "DEEPSEEK_MODEL=deepseek-v4-pro",
                "DEEPSEEK_FAST_MODEL=deepseek-v4-flash",
                "MODEL_CONTEXT_LIMIT=1000000",
            ]
        ),
        encoding="utf-8",
    )

    response = read_runtime_config(env_path)

    assert response.deepseek_api_key_configured is True
    assert response.deepseek_api_key_masked == "sk-te...alue"
    assert "secret" not in response.model_dump_json()


def test_update_runtime_config_writes_env_and_refreshes_settings_cache(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "DEEPSEEK_API_KEY=\nDEEPSEEK_MODEL=deepseek-v4-pro\nMODEL_CONTEXT_LIMIT=1000000\n",
        encoding="utf-8",
    )

    response = update_runtime_config(
        RuntimeConfigUpdateRequest(
            deepseek_api_key="sk-new-secret",
            deepseek_base_url="https://example.deepseek.test",
            deepseek_model="deepseek-v4-pro",
            deepseek_fast_model="deepseek-v4-flash",
            model_context_limit=123456,
        ),
        env_path,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-new-secret" in content
    assert "DEEPSEEK_BASE_URL=https://example.deepseek.test" in content
    assert "MODEL_CONTEXT_LIMIT=123456" in content
    assert response.deepseek_api_key_configured is True
    assert response.deepseek_api_key_masked == "sk-ne...cret"
    assert get_settings.cache_info().currsize == 0


def test_config_endpoint_does_not_return_raw_secret() -> None:
    with TestClient(app) as client:
        response = client.get("/config/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert "deepseek_api_key_configured" in payload
    assert "deepseek_api_key" not in payload
