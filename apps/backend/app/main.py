"""FastAPI application factory — registers middleware and routers."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.audit import write_audit  # noqa: F401 — re-exported for backward compat
from app.config import BackendSettings
from app.db import Base, engine
from app.routers.company import router as company_router
from app.routers.rfq import router as rfq_router
from app.schemas import APIConfigResponse, ChatResponse, ChatRequest, HealthResponse
from app.security import get_security_context  # noqa: F401 — re-exported for backward compat
from app.services.llm_service import BackendAPIError, LLMService, build_provider
from fastapi import HTTPException
from uuid import uuid4


settings = BackendSettings.from_env()
llm_service = LLMService(
    provider=build_provider(settings),
    timeout_seconds=settings.openai_timeout_seconds,
)

logger = logging.getLogger("backend.api")

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def init_db() -> None:
    # NOTE: create_all is a development convenience only.
    # In production, run: alembic upgrade head
    Base.metadata.create_all(bind=engine)


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


app.include_router(rfq_router)
app.include_router(company_router)


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service="backend", project=settings.app_name)


@app.get("/api/config", response_model=APIConfigResponse)
def api_config() -> APIConfigResponse:
    return APIConfigResponse(
        project=settings.app_name,
        llmProvider=settings.llm_provider,
        model=settings.openai_model,
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
