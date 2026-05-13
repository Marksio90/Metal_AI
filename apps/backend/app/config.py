"""Backend configuration values."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class BackendSettings:
    """Runtime settings for backend app."""

    project: str = "Metal_AI"
    default_model: str = "gpt-4.1-mini"
    provider: str = "openai"
    request_timeout_seconds: float = 20.0
    cors_allow_origins: list[str] = field(default_factory=lambda: ["*"])
