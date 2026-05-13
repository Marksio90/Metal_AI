"""FastAPI backend entrypoint with API routes and middleware."""

from __future__ import annotations

import logging
import time
from uuid import uuid4
from dataclasses import asdict
from pydantic import BaseModel, ValidationError

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Header, Depends
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
    CompanyConfigRequest,
    CompanyConfigResponse,
    AttachmentMetadataResponse,
    RiskFlagResponse,
)
from app.services.llm_service import BackendAPIError, LLMService, build_provider
from app.db import Base, SessionLocal, engine
from app.persistence_models import AuditLog, CompanyConfig, EstimatorFeedback, QuoteDraft, RFQ, RFQAttachmentMetadata
from app.persistence_models import EstimatorFeedback, QuoteDraft, RFQ, RFQAttachmentMetadata
from metal_calc.engine.rfq_intake import check_rfq_completeness
from metal_calc.engine.risk_rules import evaluate_rfq_risk_flags
from metal_calc.costing import calculate_preliminary_cost, load_company_rates
from metal_calc.models import CustomerInfo, FinishSpec, MaterialSpec, PartSpec, QuantityBreak, RFQInput, OperationType
from metal_calc.routing import generate_route
from metal_calc.knowledge import classify_operation, get_preferred_work_centers
from metal_calc.time_estimation import OperationTimeEstimator
from pypdf import PdfReader
from io import BytesIO




def get_security_context(
    x_org_id: str = Header(default="default-org"),
    x_user_id: str = Header(default="system"),
    x_role: str = Header(default="viewer"),
) -> dict:
    allowed_roles = {"admin", "estimator", "sales", "viewer"}
    if x_role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Invalid role")
    return {"org_id": x_org_id, "user_id": x_user_id, "role": x_role}


def write_audit(db, ctx: dict, action: str, resource_type: str, resource_id: str, details: dict) -> None:
    db.add(AuditLog(organization_id=ctx["org_id"], actor_id=ctx["user_id"], actor_role=ctx["role"], action=action, resource_type=resource_type, resource_id=resource_id, details=details))

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
    text = payload.message or ""

    # Lightweight deterministic extraction fallback.
    lower = text.lower()
    quantity = payload.quantity
    if quantity is None:
        import re

        match = re.search(r"\b(\d{1,7})\s*(pcs|szt|pieces)?\b", lower)
        quantity = int(match.group(1)) if match else None

    material = "steel" if any(k in lower for k in ["steel", "stal", "s235", "inox", "aluminium", "aluminum"]) else None
    finish = "painting" if any(k in lower for k in ["paint", "powder", "malow"]) else ("galvanizing" if "cynk" in lower or "galvan" in lower else None)

    extracted_ops = []
    for token in ["laser", "bending", "gię", "weld", "spaw", "pack", "pakow", "assembly", "montaż"]:
        if token in lower:
            extracted_ops.append(token)

    operation_names = extracted_ops or ["manual review"]
    estimator = OperationTimeEstimator()
    detected_operations = []
    suggested_route: list[str] = []
    for op_name in operation_names:
        cls = classify_operation(op_name)
        preferred = get_preferred_work_centers(cls.canonicalOperationType)
        estimate = estimator.estimate(cls.canonicalOperationType, preferred[0] if preferred else None)
        detected_operations.append(
            {
                "operationType": estimate["operationType"],
                "workCenter": estimate["workCenter"],
                "estimatedSeconds": estimate["estimatedSeconds"],
                "sampleCount": estimate["sampleCount"],
                "confidence": estimate["confidence"],
            }
        )
        suggested_route.append(cls.canonicalOperationType)

    missing: list[str] = []
    if not material:
        missing.append("material")
    if not quantity or quantity <= 0:
        missing.append("quantity")
    if not finish:
        missing.append("finish")
    if not payload.attachments:
        missing.append("drawing_attachment")

    risk_flags: list[str] = []
    if "drawing_attachment" in missing:
        risk_flags.append("no_drawing_provided")
    if any(op["confidence"] in {"low", "insufficient"} for op in detected_operations):
        risk_flags.append("low_historical_operation_confidence")

    requires_human_review = bool(missing) or any(op["confidence"] != "high" for op in detected_operations)
    confidence = 0.9 if not requires_human_review else 0.45

    return RFQAnalyzeResponse(
        rfqId=rfq_id,
        detectedOperations=detected_operations,
        missingInformation=missing,
        riskFlags=risk_flags,
        requiresHumanReview=requires_human_review,
        suggestedRoute=suggested_route,
        detectedParts=[],
        internalNotes=["Deterministic RFQ analysis with historical baseline-driven operation timing."],
        customerQuestions=[f"Please provide missing: {m}." for m in missing],
        draftCustomerReply="Please provide missing RFQ data." if missing else "RFQ analyzed. Ready for estimator review.",
        preliminaryCost=None,
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
def save_rfq_analysis(payload: SaveRFQAnalysisRequest, ctx: dict = Depends(get_security_context)) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = RFQ(organization_id=ctx["org_id"], rfq_id=payload.analysis.rfqId, customer=payload.customer, message=payload.message)
        write_audit(db, ctx, "save_analysis", "rfq", payload.analysis.rfqId, {"customer": payload.customer})
        db.add(row)
        db.commit()
    finally:
        db.close()
    return {"saved": True, "rfqId": payload.analysis.rfqId}


@app.post("/api/rfq/save-quote-draft")
def save_quote_draft(payload: QuoteDraftRequest, ctx: dict = Depends(get_security_context)) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = QuoteDraft(
            organization_id=ctx["org_id"],
            rfq_id=payload.rfqAnalysis.rfqId,
            customer_facing_response=payload.rfqAnalysis.draftCustomerReply,
            internal_notes={"notes": payload.rfqAnalysis.internalNotes},
            assumptions={"items": payload.rfqAnalysis.customerQuestions},
            clarification_questions={"items": payload.rfqAnalysis.customerQuestions},
            risk_warnings={"items": payload.rfqAnalysis.riskFlags},
            is_preliminary=len(payload.rfqAnalysis.missingInformation) > 0,
        )
        db.add(row)
        write_audit(db, ctx, "save_quote_draft", "quote_draft", payload.rfqAnalysis.rfqId, {})
        db.commit()
    finally:
        db.close()
    return {"saved": True, "rfqId": payload.rfqAnalysis.rfqId}


@app.post("/api/rfq/feedback")
def save_feedback(payload: EstimatorFeedbackRequest, ctx: dict = Depends(get_security_context)) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = EstimatorFeedback(
            organization_id=ctx["org_id"],
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
def feedback_diff(rfq_id: str, ctx: dict = Depends(get_security_context)) -> FeedbackDiffResponse:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        feedback = db.query(EstimatorFeedback).filter(EstimatorFeedback.rfq_id == rfq_id, EstimatorFeedback.organization_id == ctx["org_id"]).order_by(EstimatorFeedback.id.desc()).first()
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
async def upload_attachment(rfq_id: str = Form(...), file: UploadFile = File(...), ctx: dict = Depends(get_security_context)) -> AttachmentMetadataResponse:
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
            organization_id=ctx["org_id"],
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


@app.post("/api/company/config", response_model=CompanyConfigResponse)
def upsert_company_config(payload: CompanyConfigRequest, ctx: dict = Depends(get_security_context)) -> CompanyConfigResponse:
    if ctx["role"] not in {"admin"}:
        raise HTTPException(status_code=403, detail="Admin role required")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = db.query(CompanyConfig).filter(CompanyConfig.organization_id == ctx["org_id"]).first()
        if row is None:
            row = CompanyConfig(organization_id=ctx["org_id"], company_name=payload.companyName, default_currency=payload.defaultCurrency, default_language=payload.defaultLanguage)
            db.add(row)
        else:
            row.company_name = payload.companyName
            row.default_currency = payload.defaultCurrency
            row.default_language = payload.defaultLanguage
        write_audit(db, ctx, "upsert_company_config", "company_config", ctx["org_id"], payload.model_dump())
        db.commit()
        return CompanyConfigResponse(organizationId=ctx["org_id"], companyName=row.company_name, defaultCurrency=row.default_currency, defaultLanguage=row.default_language)
    finally:
        db.close()


@app.get("/api/company/config", response_model=CompanyConfigResponse)
def get_company_config(ctx: dict = Depends(get_security_context)) -> CompanyConfigResponse:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = db.query(CompanyConfig).filter(CompanyConfig.organization_id == ctx["org_id"]).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Company config not found")
        return CompanyConfigResponse(organizationId=ctx["org_id"], companyName=row.company_name, defaultCurrency=row.default_currency, defaultLanguage=row.default_language)
    finally:
        db.close()

