from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class RawOperationRow:
    sourceFile: str
    sheetName: str
    originalOperationName: str
    workCenter: str | None
    timeSeconds: float | None
    setupTimeSeconds: float | None
    ratePresent: bool
    overheadPresent: bool


@dataclass(slots=True)
class NormalizedLegacyRecord:
    source: str
    operationType: str
    originalOperationName: str
    workCenter: str | None
    timeSeconds: float | None
    setupTimeSeconds: float | None
    ratePresent: bool
    overheadPresent: bool
    materialCostDetected: bool
    packagingCostDetected: bool
    costSummaryDetected: bool

    def to_dict(self) -> dict:
        return asdict(self)
