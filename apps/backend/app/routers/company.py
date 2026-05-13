"""Company configuration endpoints (admin-only write, any role read)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.audit import write_audit
from app.db import SessionLocal
from app.persistence_models import CompanyConfig
from app.schemas import CompanyConfigRequest, CompanyConfigResponse
from app.security import get_security_context

router = APIRouter(prefix="/api/company", tags=["company"])


@router.post("/config", response_model=CompanyConfigResponse)
def upsert_company_config(
    payload: CompanyConfigRequest,
    ctx: dict = Depends(get_security_context),
) -> CompanyConfigResponse:
    if ctx["role"] not in {"admin"}:
        raise HTTPException(status_code=403, detail="Admin role required")
    db = SessionLocal()
    try:
        row = db.query(CompanyConfig).filter(CompanyConfig.organization_id == ctx["org_id"]).first()
        if row is None:
            row = CompanyConfig(
                organization_id=ctx["org_id"],
                company_name=payload.companyName,
                default_currency=payload.defaultCurrency,
                default_language=payload.defaultLanguage,
            )
            db.add(row)
        else:
            row.company_name = payload.companyName
            row.default_currency = payload.defaultCurrency
            row.default_language = payload.defaultLanguage
        write_audit(db, ctx, "upsert_company_config", "company_config", ctx["org_id"], payload.model_dump())
        db.commit()
        return CompanyConfigResponse(
            organizationId=ctx["org_id"],
            companyName=row.company_name,
            defaultCurrency=row.default_currency,
            defaultLanguage=row.default_language,
        )
    finally:
        db.close()


@router.get("/config", response_model=CompanyConfigResponse)
def get_company_config(ctx: dict = Depends(get_security_context)) -> CompanyConfigResponse:
    db = SessionLocal()
    try:
        row = db.query(CompanyConfig).filter(CompanyConfig.organization_id == ctx["org_id"]).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Company config not found")
        return CompanyConfigResponse(
            organizationId=ctx["org_id"],
            companyName=row.company_name,
            defaultCurrency=row.default_currency,
            defaultLanguage=row.default_language,
        )
    finally:
        db.close()
