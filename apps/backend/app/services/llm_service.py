"""LLM integration layer with explicit provider abstraction."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import httpx

from app.schemas import ChatMessage, ServiceChatResponse, Usage


class BackendAPIError(Exception):
    def __init__(self, frontend_message: str, status_code: int = 502) -> None:
        self.frontend_message = frontend_message
        self.status_code = status_code
        super().__init__(frontend_message)


class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(self, message: str, history: list[ChatMessage]) -> dict: ...


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "mock-llm") -> None:
        self.model_name = model_name

    async def chat(self, message: str, history: list[ChatMessage]) -> dict:
        del history
        await asyncio.sleep(0)
        prompt_tokens = len(message.split())
        return {
            "message": f"[MOCK:{self.model_name}] {message}",
            "model": self.model_name,
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 12},
        }


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str, base_url: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def chat(self, message: str, history: list[ChatMessage]) -> dict:
        if not self.api_key:
            raise BackendAPIError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.", status_code=500)

        messages = [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": message})

        payload = {"model": self.model_name, "input": messages}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/responses", json=payload, headers=headers)

        if response.status_code >= 400:
            raise BackendAPIError("OpenAI request failed. Verify model/key and retry.", status_code=502)

        data = response.json()
        text = data.get("output_text") or ""
        usage = data.get("usage", {})
        return {"message": text, "model": self.model_name, "usage": usage}


class LLMService:
    def __init__(self, provider: BaseLLMProvider, timeout_seconds: float = 20.0) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    async def chat(self, message: str, conversation_id: str, history: list[ChatMessage]) -> ServiceChatResponse:
        del conversation_id
        try:
            raw_response = await asyncio.wait_for(
                self.provider.chat(message=message, history=history), timeout=self.timeout_seconds
            )
        except TimeoutError as exc:
            raise BackendAPIError("LLM request timed out. Please try again.", status_code=504) from exc
        except BackendAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BackendAPIError("LLM provider is currently unavailable. Please retry shortly.", status_code=502) from exc

        usage = self._normalize_usage(raw_response.get("usage", {}))
        return ServiceChatResponse(
            message=raw_response.get("message", ""),
            model=raw_response.get("model", "unknown"),
            usage=usage,
        )

    def _normalize_usage(self, usage: dict) -> Usage:
        input_tokens = usage.get("inputTokens") or usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        output_tokens = usage.get("outputTokens") or usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total_tokens = usage.get("totalTokens") or usage.get("total_tokens")
        if total_tokens is None:
            total_tokens = int(input_tokens) + int(output_tokens)
        return Usage(inputTokens=int(input_tokens), outputTokens=int(output_tokens), totalTokens=int(total_tokens))


def build_provider(settings) -> BaseLLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider(model_name=settings.openai_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
