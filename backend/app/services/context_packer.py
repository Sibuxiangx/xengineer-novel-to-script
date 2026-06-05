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
    budget_tokens: int = Field(..., description="Effective token budget used for packing.")


class PackedContext(BaseModel):
    content: str = Field(..., description="Packed context content sent to the model.")
    report: ContextPackingReport = Field(..., description="Packing report for diagnostics.")


class ContextPacker:
    """Budget-aware prompt context packer."""

    def pack(self, blocks: list[ContextBlock], budget: int) -> ContextPackingReport:
        selected = self._select(blocks, budget)
        return selected.report

    def pack_content(self, blocks: list[ContextBlock], budget: int) -> PackedContext:
        return self._select(blocks, budget)

    def _select(self, blocks: list[ContextBlock], budget: int) -> PackedContext:
        included: list[str] = []
        omitted: list[str] = []
        included_blocks: list[ContextBlock] = []
        total = 0
        ordered = sorted(blocks, key=lambda block: (not block.required, -block.priority))
        for block in ordered:
            if block.required or total + block.estimated_tokens <= budget:
                included.append(block.id)
                included_blocks.append(block)
                total += block.estimated_tokens
            else:
                omitted.append(block.id)
        content = "\n\n".join(
            f"## {block.type}: {block.id}\n{block.content}" for block in included_blocks
        )
        return PackedContext(
            content=content,
            report=ContextPackingReport(
                included_block_ids=included,
                omitted_block_ids=omitted,
                estimated_tokens=total,
                budget_tokens=budget,
            ),
        )
