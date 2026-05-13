"""LLM integration layer for backend API responsibilities."""

from __future__ import annotations

import asyncio

from app.schemas import ChatMessage, ServiceChatResponse, Usage


class BackendAPIError(Exception):
    """Error shape intended for frontend-friendly API responses."""

    def __init__(self, frontend_message: str, status_code: int = 502) -> None:
        self.frontend_message = frontend_message
        self.status_code = status_code
        super().__init__(frontend_message)


class LLMService:
    """LLM service adapter with timeout and usage normalization."""

    def __init__(self, model_name: str, provider: str, timeout_seconds: float = 20.0) -> None:
        self.model_name = model_name
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    async def chat(
        self,
        message: str,
        conversation_id: str,
        history: list[ChatMessage],
    ) -> ServiceChatResponse:
        del conversation_id
        del history

        try:
            raw_response = await asyncio.wait_for(
                self._provider_chat(message=message),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            raise BackendAPIError("LLM request timed out. Please try again.", status_code=504) from exc
        except BackendAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BackendAPIError(
                "LLM provider is currently unavailable. Please retry shortly.",
                status_code=502,
            ) from exc

        usage = self._normalize_usage(raw_response.get("usage", {}))
        return ServiceChatResponse(
            message=raw_response.get("message", ""),
            model=raw_response.get("model", self.model_name),
            usage=usage,
        )

    async def _provider_chat(self, message: str) -> dict:
        """Provider SDK call placeholder."""
        await asyncio.sleep(0)
        return {
            "message": f"[{self.model_name}] {message}",
            "model": self.model_name,
            "usage": {
                "prompt_tokens": len(message.split()),
                "completion_tokens": 16,
                "total_tokens": len(message.split()) + 16,
            },
        }

    def _normalize_usage(self, usage: dict) -> Usage:
        input_tokens = usage.get("inputTokens") or usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        output_tokens = (
            usage.get("outputTokens")
            or usage.get("completion_tokens")
            or usage.get("output_tokens")
            or 0
        )
        total_tokens = usage.get("totalTokens") or usage.get("total_tokens")
        if total_tokens is None:
            total_tokens = int(input_tokens) + int(output_tokens)

        return Usage(
            inputTokens=int(input_tokens),
            outputTokens=int(output_tokens),
            totalTokens=int(total_tokens),
        )
