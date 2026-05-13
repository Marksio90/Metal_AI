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
    RFQIntakeRequest,
    RFQIntakeResponse,
    RiskFlagResponse,
)
from app.services.llm_service import BackendAPIError, LLMService, build_provider
from metal_calc.engine.rfq_intake import check_rfq_completeness
from metal_calc.engine.risk_rules import evaluate_rfq_risk_flags

settings = BackendSettings.from_env()
llm_service = LLMService(
    provider=build_provider(settings),
    timeout_seconds=settings.openai_timeout_seconds,
)

logger = logging.getLogger("backend.api")

app = FastAPI(title=settings.app_name)

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


@app.post("/api/rfq/intake-check", response_model=RFQIntakeResponse)
def rfq_intake_check(payload: RFQIntakeRequest) -> RFQIntakeResponse:
    intake = check_rfq_completeness(payload.rfqData)
    risk_flags = evaluate_rfq_risk_flags(payload.rfqData)
    return RFQIntakeResponse(
        status=intake.status.value,
        readyForCalculation=intake.ready_for_calculation,
        missingCritical=intake.missing_critical,
        missingAdvisory=intake.missing_advisory,
        warnings=intake.warnings,
        riskFlags=[
            RiskFlagResponse(code=f.code, severity=f.severity, message=f.message)
            for f in risk_flags
        ],
    )
