from pathlib import Path

from app.services.token_counter import TokenCounter


def test_token_counter_uses_bundled_deepseek_tokenizer() -> None:
    counter = TokenCounter()

    estimate = counter.estimate("请生成结构化剧本 YAML")

    assert counter.tokenizer_path.exists()
    assert counter.tokenizer_path.name == "deepseek-v4-flash-tokenizer.json"
    assert estimate.estimated_tokens > 0
    assert estimate.method == "huggingface_tokenizers:deepseek-ai/DeepSeek-V4-Flash"


def test_token_counter_falls_back_when_tokenizer_file_is_missing() -> None:
    counter = TokenCounter(tokenizer_path=Path("/tmp/scriptweaver-missing-tokenizer.json"))

    estimate = counter.estimate("结构化剧本")

    assert estimate.estimated_tokens >= len("结构化剧本")
    assert estimate.method.startswith("character_ratio_fallback:")
