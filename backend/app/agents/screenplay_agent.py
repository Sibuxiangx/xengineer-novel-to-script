from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


class ScreenplayAgent:
    """Thin boundary for the future Pydantic AI screenplay agent."""

    def load_prompt(self, prompt_name: str) -> str:
        prompt_path = PROMPT_DIR / prompt_name
        return prompt_path.read_text(encoding="utf-8")

