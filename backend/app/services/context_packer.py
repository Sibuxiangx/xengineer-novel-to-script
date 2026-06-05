from pydantic import BaseModel, Field


class ContextBlock(BaseModel):
    id: str = Field(..., description="Context block identifier.")
    type: str = Field(..., description="Context block type.")
    content: str = Field(..., description="Context block content.")
    priority: int = Field(..., description="Higher priority blocks are packed first.")
    estimated_tokens: int = Field(..., description="Estimated token cost.")
    required: bool = Field(False, description="Whether this block must be included.")


class ContextPackingReport(BaseModel):
    included_block_ids: list[str] = Field(..., description="IDs included in packed context.")
    omitted_block_ids: list[str] = Field(..., description="IDs omitted due to budget.")
    estimated_tokens: int = Field(..., description="Total estimated tokens in packed context.")


class ContextPacker:
    """Budget-aware prompt context packer."""

    def pack(self, blocks: list[ContextBlock], budget: int) -> ContextPackingReport:
        included: list[str] = []
        omitted: list[str] = []
        total = 0
        ordered = sorted(blocks, key=lambda block: (not block.required, -block.priority))
        for block in ordered:
            if block.required or total + block.estimated_tokens <= budget:
                included.append(block.id)
                total += block.estimated_tokens
            else:
                omitted.append(block.id)
        return ContextPackingReport(
            included_block_ids=included,
            omitted_block_ids=omitted,
            estimated_tokens=total,
        )

