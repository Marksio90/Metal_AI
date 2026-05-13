"""Backend configuration values loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class BackendSettings:
    app_name: str
    app_env: str
    cors_allow_origins: list[str]
    llm_provider: str
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    openai_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "BackendSettings":
        origins_raw = os.getenv("BACKEND_CORS_ALLOW_ORIGINS", "*")
        origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
        return cls(
            app_name=os.getenv("APP_NAME", "Metal_AI"),
            app_env=os.getenv("APP_ENV", "development"),
            cors_allow_origins=origins or ["*"],
            llm_provider=os.getenv("LLM_PROVIDER", "mock").lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20")),
        )
