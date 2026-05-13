from __future__ import annotations

from metal_calc.knowledge import classify_operation, get_preferred_work_centers
from metal_calc.time_estimation import OperationTimeEstimator
from metal_calc.models import (
    ConfidenceScore,
    ManufacturingOperation,
    ManufacturingRoute,
    OperationType,
    RFQInput,
    RiskFlag,
)
from metal_calc.validators import detect_missing_information


def suggest_route_from_context(
    *,
    rfq_text: str,
    material_type: str | None,
    geometry_hints: list[str] | None,
    finish_type: str | None,
    shippable: bool = True,
) -> list[dict]:
    """Suggest canonical operation route with preferred work centers and baseline hints."""

    text = (rfq_text or "").lower()
    hints = [h.lower() for h in (geometry_hints or [])]
    joined = " ".join([text] + hints)

    candidates: list[str] = []

    if any(k in joined for k in ["laser", "cię", "cut"]) and any(k in joined for k in ["sheet", "blacha"]):
        candidates.append("laser_sheet_cutting")
    if any(k in joined for k in ["bend", "gię"]) and any(k in joined for k in ["sheet", "blacha"]):
        candidates.append("cnc_bending_sheet")
    if any(k in joined for k in ["wire", "drut"]) and any(k in joined for k in ["bend", "gię"]):
        candidates.append("cnc_bending_wire")
    if any(k in joined for k in ["wire", "drut"]) and any(k in joined for k in ["straight", "prost", "cut", "cię"]):
        candidates.append("wire_straightening_cutting")
    if "robot" in joined and any(k in joined for k in ["weld", "spaw"]):
        candidates.append("robot_welding")
    elif any(k in joined for k in ["weld", "spaw"]):
        candidates.append("mig_manual_welding")
    if any(k in joined for k in ["zgrzew", "spot"]):
        candidates.append("spot_welding")
    if any(k in joined for k in ["ral", "powder", "malow"]):
        candidates.append("painting")

    if material_type and material_type.lower() in {"sheet", "blacha"} and "laser_sheet_cutting" not in candidates:
        candidates.append("laser_sheet_cutting")

    if shippable and "packaging" not in candidates:
        candidates.append("packaging")

    if not candidates:
        candidates = ["manual_review"]

    estimator = OperationTimeEstimator()
    route = []
    for canonical_op in candidates:
        preferred = get_preferred_work_centers(canonical_op)
        est = estimator.estimate(canonical_op, preferred[0] if preferred else None)
        route.append(
            {
                "operationType": canonical_op,
                "workCenter": est.get("workCenter") or (preferred[0] if preferred else None),
                "estimatedSeconds": est.get("estimatedSeconds"),
                "confidence": est.get("confidence"),
                "sampleCount": est.get("sampleCount", 0),
            }
        )
    return route


def generate_route(rfq: RFQInput) -> ManufacturingRoute:
    missing = detect_missing_information(rfq)
    operations: list[ManufacturingOperation] = []
    assumptions: list[str] = ["Route generated using deterministic context rules and historical baselines."]
    risks: list[RiskFlag] = []

    for op in rfq.requested_operations:
        operations.append(ManufacturingOperation(operation=op, assumptions=["Requested by user."]))

    if not operations:
        # Build from RFQ context and map canonical types to current enum set.
        text = f"{rfq.material.material_code} {rfq.finish.finish_code} {rfq.part.part_name}"
        suggestions = suggest_route_from_context(
            rfq_text=text,
            material_type=rfq.material.material_code,
            geometry_hints=[rfq.part.geometry_ref or ""],
            finish_type=rfq.finish.finish_code,
            shippable=rfq.quantity_break.quantity > 0,
        )
        mapping = {
            "laser_sheet_cutting": OperationType.LASER_CUTTING,
            "laser_tube_or_profile_cutting": OperationType.LASER_CUTTING,
            "saw_or_profile_cutting": OperationType.LASER_CUTTING,
            "cnc_bending_sheet": OperationType.BENDING,
            "cnc_bending_tube": OperationType.BENDING,
            "cnc_bending_wire": OperationType.BENDING,
            "wire_straightening_cutting": OperationType.BENDING,
            "mig_manual_welding": OperationType.WELDING,
            "robot_welding": OperationType.WELDING,
            "spot_welding": OperationType.WELDING,
            "deburring_manual_finishing": OperationType.DEBURRING,
            "grinding": OperationType.DEBURRING,
            "assembly": OperationType.ASSEMBLY,
            "packaging": OperationType.SUBCONTRACTING,
            "pressing": OperationType.SUBCONTRACTING,
            "milling": OperationType.SUBCONTRACTING,
            "drilling": OperationType.SUBCONTRACTING,
            "turning": OperationType.SUBCONTRACTING,
            "painting": OperationType.PAINTING,
            "galvanizing": OperationType.GALVANIZING,
            "subcontracting": OperationType.SUBCONTRACTING,
            "manual_review": OperationType.MANUAL_REVIEW,
            "unknown_operation": OperationType.MANUAL_REVIEW,
        }
        for s in suggestions:
            op_enum = mapping.get(s["operationType"], OperationType.MANUAL_REVIEW)
            operations.append(ManufacturingOperation(operation=op_enum, assumptions=[f"Suggested center: {s.get('workCenter')}"]))

    if missing.fields:
        risks.append(RiskFlag(code="MISSING_DATA", severity="high", message="RFQ has missing core fields."))

    confidence_value = 0.9 if not missing.fields else 0.4
    confidence = ConfidenceScore(value=confidence_value, rationale="Reduced when required fields are missing.")
    return ManufacturingRoute(operations=operations, confidence=confidence, risks=risks, assumptions=assumptions)
