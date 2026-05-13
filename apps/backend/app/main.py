"""FastAPI backend entrypoint with API routes and middleware."""

from __future__ import annotations

import logging
import time
from uuid import uuid4
from dataclasses import asdict
from pydantic import BaseModel, ValidationError

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
    RFQAnalyzeRequest,
    RFQAnalyzeResponse,
    QuoteDraftRequest,
    QuoteDraftResponse,
    RiskFlagResponse,
)
from app.services.llm_service import BackendAPIError, LLMService, build_provider
from metal_calc.engine.rfq_intake import check_rfq_completeness
from metal_calc.engine.risk_rules import evaluate_rfq_risk_flags
from metal_calc.costing import calculate_preliminary_cost, load_company_rates
from metal_calc.models import CustomerInfo, FinishSpec, MaterialSpec, PartSpec, QuantityBreak, RFQInput, OperationType
from metal_calc.routing import generate_route


class RFQExtractionResult(BaseModel):
    detectedParts: list[dict] = []
    material: str | None = None
    thicknessMm: float | None = None
    quantity: int | None = None
    finish: str | None = None
    toleranceRisk: bool = False
    operations: list[str] = []

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


@app.post("/api/rfq/analyze", response_model=RFQAnalyzeResponse)
async def analyze_rfq(payload: RFQAnalyzeRequest) -> RFQAnalyzeResponse:
    rfq_id = str(uuid4())
    try:
        extracted_raw = await llm_service.extract_rfq_structured(payload.message)
        extracted = RFQExtractionResult.model_validate(extracted_raw)
    except (BackendAPIError, ValidationError):
        raise HTTPException(status_code=502, detail="RFQ analysis failed safely. Please verify input and retry.")

    missing: list[str] = []
    if not extracted.material or extracted.material == "unknown_material":
        missing.append("material")
    if extracted.thicknessMm is None:
        missing.append("thickness_mm")
    if (payload.quantity or extracted.quantity or 0) <= 0:
        missing.append("quantity")
    if not extracted.finish:
        missing.append("finishing_details")
    if not payload.attachments:
        missing.append("drawing_attachment")

    risks: list[str] = []
    if extracted.toleranceRisk:
        risks.append("risky_tolerances")
    if "drawing_attachment" in missing:
        risks.append("no_drawing_provided")

    suggested_route = extracted.operations or ["manual_review"]

    internal_notes = ["Deterministic post-processing applied to LLM extraction output."]
    preliminary_cost = None
    try:
        rfq_input = RFQInput(
            customer=CustomerInfo(name=payload.customer),
            part=PartSpec(part_name="part_1", mass_kg=1.0),
            material=MaterialSpec(material_code=extracted.material or "unknown_material", thickness_mm=extracted.thicknessMm),
            finish=FinishSpec(finish_code=extracted.finish or "unknown_finish"),
            quantity_break=QuantityBreak(quantity=payload.quantity or extracted.quantity or 0),
            requested_operations=[OperationType(op) for op in suggested_route if op in {e.value for e in OperationType}],
        )
        route = generate_route(rfq_input)
        rates = load_company_rates()
        preliminary_cost = asdict(calculate_preliminary_cost(rfq_input, route, rates))
    except Exception as exc:
        internal_notes.append(f"Preliminary costing skipped due to incomplete structured data: {type(exc).__name__}.")
    customer_questions = [f"Please provide missing: {m}." for m in missing]
    confidence = 0.85 if not missing else 0.45

    draft_reply = "Thank you for your RFQ. To prepare a reliable quotation, please provide: " + ", ".join(missing) + "." if missing else "Thank you for your RFQ. We have enough initial data and will send a quotation draft shortly."

    return RFQAnalyzeResponse(
        rfqId=rfq_id,
        detectedParts=extracted.detectedParts,
        missingInformation=missing,
        suggestedRoute=suggested_route,
        riskFlags=risks,
        internalNotes=internal_notes,
        customerQuestions=customer_questions,
        draftCustomerReply=draft_reply,
        preliminaryCost=preliminary_cost,
        confidence=confidence,
    )


@app.post("/api/rfq/quote-draft", response_model=QuoteDraftResponse)
def quote_draft(payload: QuoteDraftRequest) -> QuoteDraftResponse:
    analysis = payload.rfqAnalysis
    is_preliminary = len(analysis.missingInformation) > 0

    assumptions = [
        "Draft generated from RFQ analysis output.",
        "Commercial terms, delivery and validity are subject to final technical review.",
    ]
    if is_preliminary:
        assumptions.append("Draft is preliminary due to missing RFQ information.")

    clarification_questions = [q for q in analysis.customerQuestions]
    risk_warnings = [r for r in analysis.riskFlags]

    if payload.language.lower().startswith("pl"):
        opening = "Dziękujemy za zapytanie ofertowe."
        prelim = "Oferta ma charakter wstępny" if is_preliminary else "Możemy przygotować ofertę"
    else:
        opening = "Thank you for your RFQ."
        prelim = "This quotation is preliminary" if is_preliminary else "We can prepare a formal quotation"

    customer_lines = [
        opening,
        f"{prelim} based on current data.",
    ]
    if clarification_questions:
        customer_lines.append("To proceed, please clarify:")
        customer_lines.extend([f"- {q}" for q in clarification_questions])
    customer_lines.append("Best regards,")
    customer_lines.append("Sales Team")

    internal_notes = list(analysis.internalNotes)
    if payload.costBreakdown or analysis.preliminaryCost:
        internal_notes.append("Cost breakdown available internally; do not disclose margin structure to customer.")
    if is_preliminary:
        internal_notes.append("Do not commit to final price before missing technical data is received.")

    return QuoteDraftResponse(
        customerFacingResponse="\n".join(customer_lines),
        internalEstimatorNotes=internal_notes,
        assumptions=assumptions,
        clarificationQuestions=clarification_questions,
        riskWarnings=risk_warnings,
        isPreliminary=is_preliminary,
    )
