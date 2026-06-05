class ScriptGenerationService:
    """Service boundary for screenplay YAML generation."""

    async def generate_placeholder(self) -> str:
        return "schema_version: '1.0'\n"

