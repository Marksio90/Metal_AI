from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from openai import OpenAIError

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_ROLES = {"user", "assistant", "system"}
MAX_HISTORY_ITEMS = 50
MAX_MESSAGE_LENGTH = 8_000


@dataclass(frozen=True)
class ServiceError(Exception):
    """Controlled service-level error for API responses."""

    status_code: int
    message: str


class LLMService:
    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER

        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ServiceError(
                    status_code=500,
                    message="LLM service is not configured.",
                )
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            raise ServiceError(status_code=400, message="Unsupported LLM provider.")

    def _sanitize_history(self, history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
        if not history:
            return []

        sanitized: list[dict[str, str]] = []
        for entry in history[:MAX_HISTORY_ITEMS]:
            role = str(entry.get("role", "")).strip().lower()
            content = str(entry.get("content", "")).strip()

            if role not in ALLOWED_ROLES:
                continue
            if not content:
                continue

            sanitized.append(
                {
                    "role": role,
                    "content": content[:MAX_MESSAGE_LENGTH],
                }
            )

        return sanitized

    def generate(self, prompt: str, history: list[dict[str, Any]] | None = None) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            raise ServiceError(status_code=400, message="Prompt cannot be empty.")

        messages = self._sanitize_history(history)
        messages.append({"role": "user", "content": prompt[:MAX_MESSAGE_LENGTH]})

        try:
            response = self._client.responses.create(
                model=settings.OPENAI_MODEL,
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_OUTPUT_TOKENS,
                input=messages,
            )
            return response.output_text
        except OpenAIError:
            logger.exception("LLM provider request failed.")
            raise ServiceError(status_code=502, message="LLM provider is unavailable.")
