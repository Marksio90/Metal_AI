"""Backend configuration values."""

from dataclasses import dataclass


@dataclass(slots=True)
class BackendSettings:
    """Runtime settings for backend app."""

    default_model: str = "gpt-4.1-mini"
    provider: str = "openai"
