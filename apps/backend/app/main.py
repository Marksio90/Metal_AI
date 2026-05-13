"""FastAPI backend entrypoint with API routes and middleware."""

from __future__ import annotations

import logging
import time
from uuid import uuid4
from dataclasses import asdict
from pydantic import BaseModel, ValidationError

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
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
    SaveRFQAnalysisRequest,
    EstimatorFeedbackRequest,
    FeedbackDiffResponse,
    AttachmentMetadataResponse,
    RiskFlagResponse,
)
from app.services.llm_service import BackendAPIError, LLMService, build_provider
from app.db import Base, SessionLocal, engine
from app.persistence_models import EstimatorFeedback, QuoteDraft, RFQ, RFQAttachmentMetadata
from metal_calc.engine.rfq_intake import check_rfq_completeness
from metal_calc.engine.risk_rules import evaluate_rfq_risk_flags
from metal_calc.costing import calculate_preliminary_cost, load_company_rates
from metal_calc.models import CustomerInfo, FinishSpec, MaterialSpec, PartSpec, QuantityBreak, RFQInput, OperationType
from metal_calc.routing import generate_route
from pypdf import PdfReader
from io import BytesIO


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

@app.on_event("startup")
def init_db() -> None:
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


@app.post("/api/rfq/save-analysis")
def save_rfq_analysis(payload: SaveRFQAnalysisRequest) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = RFQ(rfq_id=payload.analysis.rfqId, customer=payload.customer, message=payload.message)
        db.add(row)
        db.commit()
    finally:
        db.close()
    return {"saved": True, "rfqId": payload.analysis.rfqId}


@app.post("/api/rfq/save-quote-draft")
def save_quote_draft(payload: QuoteDraftRequest) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = QuoteDraft(
            rfq_id=payload.rfqAnalysis.rfqId,
            customer_facing_response=payload.rfqAnalysis.draftCustomerReply,
            internal_notes={"notes": payload.rfqAnalysis.internalNotes},
            assumptions={"items": payload.rfqAnalysis.customerQuestions},
            clarification_questions={"items": payload.rfqAnalysis.customerQuestions},
            risk_warnings={"items": payload.rfqAnalysis.riskFlags},
            is_preliminary=len(payload.rfqAnalysis.missingInformation) > 0,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()
    return {"saved": True, "rfqId": payload.rfqAnalysis.rfqId}


@app.post("/api/rfq/feedback")
def save_feedback(payload: EstimatorFeedbackRequest) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = EstimatorFeedback(
            rfq_id=payload.rfqId,
            decision=payload.decision,
            corrected_material=payload.correctedMaterial,
            corrected_operation_route={"route": payload.correctedOperationRoute} if payload.correctedOperationRoute else None,
            corrected_quantity=payload.correctedQuantity,
            corrected_cost=payload.correctedCost,
            corrected_margin=payload.correctedMargin,
            correction_reason=payload.correctionReason,
            estimator_note=payload.estimatorNote,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()
    return {"saved": True}


@app.get("/api/rfq/feedback-diff/{rfq_id}", response_model=FeedbackDiffResponse)
def feedback_diff(rfq_id: str) -> FeedbackDiffResponse:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        feedback = db.query(EstimatorFeedback).filter(EstimatorFeedback.rfq_id == rfq_id).order_by(EstimatorFeedback.id.desc()).first()
        if feedback is None:
            raise HTTPException(status_code=404, detail="No feedback found for RFQ")

        ai_suggestion = {
            "material": "unknown",
            "route": [],
            "quantity": None,
            "cost": None,
            "margin": None,
        }
        human = {
            "material": feedback.corrected_material,
            "route": (feedback.corrected_operation_route or {}).get("route", []),
            "quantity": feedback.corrected_quantity,
            "cost": feedback.corrected_cost,
            "margin": feedback.corrected_margin,
            "decision": feedback.decision,
            "reason": feedback.correction_reason,
            "note": feedback.estimator_note,
        }
        diffs = [k for k in ["material", "route", "quantity", "cost", "margin"] if human.get(k) not in (None, [], ai_suggestion.get(k))]
        return FeedbackDiffResponse(rfqId=rfq_id, aiSuggestion=ai_suggestion, humanCorrection=human, differences=diffs)
    finally:
        db.close()


@app.post("/api/rfq/upload-attachment", response_model=AttachmentMetadataResponse)
async def upload_attachment(rfq_id: str = Form(...), file: UploadFile = File(...)) -> AttachmentMetadataResponse:
    allowed_ext = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}
    max_size = 10 * 1024 * 1024
    filename = file.filename or "unknown"
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    raw = await file.read()
    if len(raw) > max_size:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

    extracted_text = None
    if ext == ".pdf":
        try:
            reader = PdfReader(BytesIO(raw))
            extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception:
            extracted_text = None

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = RFQAttachmentMetadata(
            rfq_id=rfq_id,
            filename=filename,
            extension=ext,
            size_bytes=len(raw),
            content_type=file.content_type or "application/octet-stream",
            extracted_text=extracted_text,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    return AttachmentMetadataResponse(
        rfqId=rfq_id,
        filename=filename,
        extension=ext,
        sizeBytes=len(raw),
        contentType=file.content_type or "application/octet-stream",
        extractedTextPreview=(extracted_text[:500] if extracted_text else None),
    )
