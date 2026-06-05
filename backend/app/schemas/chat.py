from pydantic import BaseModel, Field


class ProjectTitleSuggestion(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="适合作为改编项目名的中文标题。",
    )
    reason: str = Field(..., min_length=1, description="标题推导依据。")
