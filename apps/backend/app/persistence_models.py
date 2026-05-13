from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RFQ(Base):
    __tablename__ = "rfq"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True, default="default-org")
    rfq_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RFQAttachmentMetadata(Base):
    __tablename__ = "rfq_attachment_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True, default="default-org")
    rfq_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100))
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuoteDraft(Base):
    __tablename__ = "quote_draft"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True, default="default-org")
    rfq_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_facing_response: Mapped[str] = mapped_column(Text)
    internal_notes: Mapped[dict] = mapped_column(JSON)
    assumptions: Mapped[dict] = mapped_column(JSON)
    clarification_questions: Mapped[dict] = mapped_column(JSON)
    risk_warnings: Mapped[dict] = mapped_column(JSON)
    is_preliminary: Mapped[bool] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EstimatorFeedback(Base):
    __tablename__ = "estimator_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True, default="default-org")
    rfq_id: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(64))  # accepted / rejected
    corrected_material: Mapped[str | None] = mapped_column(String(128), nullable=True)
    corrected_operation_route: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    corrected_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corrected_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    corrected_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyConfig(Base):
    __tablename__ = "company_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    default_currency: Mapped[str] = mapped_column(String(8), default="PLN")
    default_language: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(128))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
