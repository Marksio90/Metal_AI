"""LLM integration layer for backend API responsibilities.

Note: backend can optionally import and orchestrate domain logic from
``src/metal_calc`` in future iterations without moving core code.
"""

from app.schemas import LLMResponse


class LLMService:
    """Minimal LLM service adapter stub."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def complete(self, prompt: str) -> LLMResponse:
        # Placeholder implementation for architecture bootstrap.
        return LLMResponse(content=f"[{self.model_name}] {prompt}")
