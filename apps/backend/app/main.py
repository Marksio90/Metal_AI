"""Backend API entrypoint.

This layer orchestrates HTTP/API responsibilities and delegates LLM work
to service modules. Domain/core logic remains in ``src/metal_calc``.
"""

from app.config import BackendSettings
from app.schemas import HealthResponse
from app.services.llm_service import LLMService


settings = BackendSettings()
llm_service = LLMService(model_name=settings.default_model)


def healthcheck() -> HealthResponse:
    """Simple health endpoint contract used by a future web framework."""
    return HealthResponse(status="ok", service="backend")
