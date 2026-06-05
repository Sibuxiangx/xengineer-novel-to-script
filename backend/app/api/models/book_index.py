from pydantic import BaseModel, Field

from app.schemas.book_index import BookIndex


class BookIndexBuildRequest(BaseModel):
    force_rebuild: bool = Field(
        False,
        description="Whether to rebuild the book index even if one already exists.",
    )


class BookIndexResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    book_index: BookIndex = Field(..., description="Generated or loaded book index.")
    file_path: str = Field(..., description="Local book_index.json path.")

