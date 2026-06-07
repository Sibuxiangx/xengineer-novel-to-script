from pydantic import BaseModel, Field


class RuntimeConfigResponse(BaseModel):
    env_file_exists: bool = Field(..., description="Whether backend/.env exists.")
    env_file_path: str = Field(..., description="Relative path of the local dotenv file.")
    deepseek_api_key_configured: bool = Field(
        ...,
        description="Whether a DeepSeek API key is available from dotenv or process env.",
    )
    deepseek_api_key_masked: str | None = Field(
        default=None,
        description="Masked DeepSeek API key for display only. The raw key is never returned.",
    )
    deepseek_base_url: str = Field(..., description="DeepSeek-compatible API base URL.")
    deepseek_model: str = Field(..., description="Primary agent model.")
    deepseek_fast_model: str = Field(..., description="Fast structured-generation model.")
    model_context_limit: int = Field(..., description="Configured context window budget.")


class RuntimeConfigUpdateRequest(BaseModel):
    deepseek_api_key: str | None = Field(
        default=None,
        description="New DeepSeek API key. Omit or send an empty string to keep the current key.",
    )
    deepseek_base_url: str | None = Field(
        default=None,
        min_length=1,
        description="DeepSeek-compatible API base URL.",
    )
    deepseek_model: str | None = Field(
        default=None,
        min_length=1,
        description="Primary agent model.",
    )
    deepseek_fast_model: str | None = Field(
        default=None,
        min_length=1,
        description="Fast structured-generation model.",
    )
    model_context_limit: int | None = Field(
        default=None,
        ge=1,
        description="Configured context window budget.",
    )
