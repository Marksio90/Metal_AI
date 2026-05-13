from __future__ import annotations

from metal_calc.knowledge import classify_operation

from .anonymizer import anonymize_filename
from .schema import NormalizedLegacyRecord, RawOperationRow
from .validator import validate_operation_row


def normalize_rows(
    *,
    source_filename: str,
    rows: list[RawOperationRow],
    material_detected: bool,
    packaging_detected: bool,
    cost_summary_detected: bool,
) -> tuple[list[NormalizedLegacyRecord], list[dict]]:
    normalized: list[NormalizedLegacyRecord] = []
    validation_issues: list[dict] = []

    for row in rows:
        errors = validate_operation_row(row)
        if errors:
            validation_issues.append({"row": row.originalOperationName, "errors": errors})
            continue

        classification = classify_operation(row.originalOperationName, row.workCenter)
        normalized.append(
            NormalizedLegacyRecord(
                source=anonymize_filename(source_filename),
                operationType=classification.canonicalOperationType,
                originalOperationName=classification.originalOperationName,
                workCenter=classification.workCenter,
                timeSeconds=row.timeSeconds,
                setupTimeSeconds=row.setupTimeSeconds,
                ratePresent=row.ratePresent,
                overheadPresent=row.overheadPresent,
                materialCostDetected=material_detected,
                packagingCostDetected=packaging_detected,
                costSummaryDetected=cost_summary_detected,
            )
        )

    return normalized, validation_issues
