from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RFQ(Base):
    __tablename__ = "rfq"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfq_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuoteDraft(Base):
    __tablename__ = "quote_draft"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
    rfq_id: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
