from __future__ import annotations

from metal_calc.knowledge import CANONICAL_OPERATION_TYPES, classify_operation


def list_canonical_operations() -> list[str]:
    return list(CANONICAL_OPERATION_TYPES)


def normalize_operation_name(original_operation_name: str, work_center: str | None = None) -> dict:
    cls = classify_operation(original_operation_name, work_center)
    return {
        "originalOperationName": cls.originalOperationName,
        "canonicalOperationType": cls.canonicalOperationType,
        "workCenter": cls.workCenter,
        "confidence": cls.confidence,
    }
