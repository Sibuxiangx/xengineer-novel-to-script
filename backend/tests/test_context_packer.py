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
            ),
        ],
        budget=50,
    )

    assert report.included_block_ids == ["schema"]
    assert report.omitted_block_ids == ["excerpt"]

