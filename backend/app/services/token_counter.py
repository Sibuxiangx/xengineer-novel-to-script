from pydantic import BaseModel, Field


class TokenEstimate(BaseModel):
    text_length: int = Field(..., description="Input text length in characters.")
    estimated_tokens: int = Field(..., description="Conservative local token estimate.")
    method: str = Field(..., description="Estimator method name.")


class TokenCounter:
    """Local fallback token estimator until the DeepSeek tokenizer is integrated."""

    def estimate(self, text: str) -> TokenEstimate:
        # Conservative Chinese text fallback: roughly one token per character plus margin.
        estimated = max(1, int(len(text) * 1.2))
        return TokenEstimate(
            text_length=len(text),
            estimated_tokens=estimated,
            method="character_ratio_fallback",
        )

