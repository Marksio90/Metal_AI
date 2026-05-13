"""Backend request/response schemas."""

from dataclasses import dataclass


@dataclass(slots=True)
class HealthResponse:
    status: str
    service: str


@dataclass(slots=True)
class LLMRequest:
    prompt: str


@dataclass(slots=True)
class LLMResponse:
    content: str
