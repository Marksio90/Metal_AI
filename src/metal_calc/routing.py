from __future__ import annotations

from metal_calc.models import (
    ConfidenceScore,
    ManufacturingOperation,
    ManufacturingRoute,
    OperationType,
    RFQInput,
    RiskFlag,
)
from metal_calc.validators import detect_missing_information


def generate_route(rfq: RFQInput) -> ManufacturingRoute:
    missing = detect_missing_information(rfq)
    operations: list[ManufacturingOperation] = []
    assumptions: list[str] = ["Route generated using deterministic v1 rules."]
    risks: list[RiskFlag] = []

    for op in rfq.requested_operations:
        operations.append(ManufacturingOperation(operation=op, assumptions=["Requested by user."]))

    if not operations:
        operations = [ManufacturingOperation(operation=OperationType.MANUAL_REVIEW, assumptions=["No operation provided."]) ]
        assumptions.append("No requested operation; defaulted to manual review.")

    if missing.fields:
        risks.append(RiskFlag(code="MISSING_DATA", severity="high", message="RFQ has missing core fields."))

    confidence_value = 0.9 if not missing.fields else 0.4
    confidence = ConfidenceScore(value=confidence_value, rationale="Reduced when required fields are missing.")
    return ManufacturingRoute(operations=operations, confidence=confidence, risks=risks, assumptions=assumptions)
