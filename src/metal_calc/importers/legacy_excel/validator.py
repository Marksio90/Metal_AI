from __future__ import annotations

from .schema import RawOperationRow


def validate_operation_row(row: RawOperationRow) -> list[str]:
    errors: list[str] = []
    if not row.originalOperationName:
        errors.append("Missing operation name")
    if row.timeSeconds is not None and row.timeSeconds < 0:
        errors.append("Negative timeSeconds")
    if row.setupTimeSeconds is not None and row.setupTimeSeconds < 0:
        errors.append("Negative setupTimeSeconds")
    return errors
