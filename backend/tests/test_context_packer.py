from app.services.context_packer import ContextBlock, ContextPacker


def test_context_packer_keeps_required_blocks_over_budget() -> None:
    packer = ContextPacker()
    report = packer.pack(
        blocks=[
            ContextBlock(
                id="schema",
                type="schema",
                content="schema",
                priority=10,
                estimated_tokens=100,
                required=True,
            ),
            ContextBlock(
                id="excerpt",
                type="source_excerpt",
                content="excerpt",
                priority=1,
                estimated_tokens=100,
                required=False,
            ),
        ],
        budget=50,
    )

    assert report.included_block_ids == ["schema"]
    assert report.omitted_block_ids == ["excerpt"]
    assert report.budget_tokens == 50


def test_context_packer_returns_packed_content_for_included_blocks() -> None:
    packer = ContextPacker()
    packed = packer.pack_content(
        blocks=[
            ContextBlock(
                id="task",
                type="task_instruction",
                content="任务说明",
                priority=10,
                estimated_tokens=10,
                required=True,
            ),
            ContextBlock(
                id="optional",
                type="source_excerpt",
                content="可选片段",
                priority=1,
                estimated_tokens=100,
                required=False,
            ),
        ],
        budget=20,
    )

    assert "## task_instruction: task" in packed.content
    assert "任务说明" in packed.content
    assert "可选片段" not in packed.content
    assert packed.report.included_block_ids == ["task"]
    assert packed.report.omitted_block_ids == ["optional"]
