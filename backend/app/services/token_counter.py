from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field
from tokenizers import Tokenizer


class TokenEstimate(BaseModel):
    text_length: int = Field(..., description="Input text length in characters.")
    estimated_tokens: int = Field(..., description="Conservative local token estimate.")
    method: str = Field(..., description="Estimator method name.")


class TokenCounter:
    """Local DeepSeek token counter backed by the bundled tokenizer.json."""

    DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-V4-Flash"
    DEFAULT_TOKENIZER_FILE = "deepseek-v4-flash-tokenizer.json"

    _cached_tokenizer: ClassVar[Tokenizer | None] = None
    _cached_path: ClassVar[Path | None] = None

    def __init__(
        self,
        *,
        tokenizer_path: Path | None = None,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        self.tokenizer_path = tokenizer_path or self._default_tokenizer_path()
        self.model_id = model_id

    def estimate(self, text: str) -> TokenEstimate:
        if text == "":
            return TokenEstimate(
                text_length=0,
                estimated_tokens=0,
                method=self._method_name("huggingface_tokenizers"),
            )

        try:
            tokenizer = self._load_tokenizer()
            token_count = len(tokenizer.encode(text, add_special_tokens=False).ids)
            estimated = max(1, token_count)
            method = self._method_name("huggingface_tokenizers")
        except Exception as exc:
            estimated = max(1, int(len(text) * 1.2))
            method = f"character_ratio_fallback:{type(exc).__name__}"
        return TokenEstimate(
            text_length=len(text),
            estimated_tokens=estimated,
            method=method,
        )

    def _load_tokenizer(self) -> Tokenizer:
        cached = self.__class__._cached_tokenizer
        if cached is not None and self.__class__._cached_path == self.tokenizer_path:
            return cached

        tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
        self.__class__._cached_tokenizer = tokenizer
        self.__class__._cached_path = self.tokenizer_path
        return tokenizer

    def _method_name(self, backend: str) -> str:
        return f"{backend}:{self.model_id}"

    @classmethod
    def _default_tokenizer_path(cls) -> Path:
        explicit_path = os.getenv("DEEPSEEK_TOKENIZER_PATH")
        if explicit_path:
            return Path(explicit_path).expanduser()
        return (
            Path(__file__).resolve().parents[1]
            / "resources"
            / "tokenizers"
            / cls.DEFAULT_TOKENIZER_FILE
        )
