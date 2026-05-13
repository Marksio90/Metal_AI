"""Backend request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    project: str


class APIConfigResponse(BaseModel):
    project: str
    llmProvider: str
    model: str


class Usage(BaseModel):
    inputTokens: int = 0
    outputTokens: int = 0
    totalTokens: int = 0


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversationId: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversationId: str
    message: str
    model: str
    usage: Usage


class ServiceChatResponse(BaseModel):
    message: str
    model: str
    usage: Usage
