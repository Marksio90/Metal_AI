"""FastAPI backend entrypoint with API routes and middleware."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import BackendSettings
from app.schemas import (
    APIConfigResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
)
from app.services.llm_service import BackendAPIError, LLMService

settings = BackendSettings()
llm_service = LLMService(
    model_name=settings.default_model,
    provider=settings.provider,
    timeout_seconds=settings.request_timeout_seconds,
)

logger = logging.getLogger("backend.api")

app = FastAPI(title=settings.project)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "%s %s -> %s (%sms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service="backend", project=settings.project)


@app.get("/api/config", response_model=APIConfigResponse)
def api_config() -> APIConfigResponse:
    return APIConfigResponse(
        project=settings.project,
        llmProvider=settings.provider,
        model=settings.default_model,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    conversation_id = payload.conversationId or str(uuid4())
    try:
        llm_result = await llm_service.chat(
            message=payload.message,
            conversation_id=conversation_id,
            history=payload.history,
        )
    except BackendAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.frontend_message) from exc

    return ChatResponse(
        conversationId=conversation_id,
        message=llm_result.message,
        model=llm_result.model,
        usage=llm_result.usage,
    )
