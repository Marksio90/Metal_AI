"""Normalized operation taxonomy and lightweight canonicalization helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import unicodedata

CANONICAL_OPERATION_TYPES = [
    "laser_sheet_cutting",
    "laser_tube_or_profile_cutting",
    "saw_or_profile_cutting",
    "cnc_bending_sheet",
    "cnc_bending_tube",
    "cnc_bending_wire",
    "wire_straightening_cutting",
    "mig_manual_welding",
    "robot_welding",
    "spot_welding",
    "deburring_manual_finishing",
    "grinding",
    "assembly",
    "packaging",
    "pressing",
    "milling",
    "drilling",
    "turning",
    "painting",
    "galvanizing",
    "subcontracting",
    "manual_review",
    "unknown_operation",
]


@dataclass(frozen=True)
class OperationClassification:
    originalOperationName: str
    canonicalOperationType: str
    workCenter: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, str | float | None]:
        return asdict(self)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _norm(value: str) -> str:
    v = _strip_accents(value).lower()
    return re.sub(r"\s+", " ", v).strip()


_RULES: list[tuple[str, str, float]] = [
    (r"\blaser\b.*\b(blacha|sheet)\b|\b(blacha|sheet)\b.*\blaser\b", "laser_sheet_cutting", 0.98),
    (r"\blaser\b.*\b(rur|profil|tube|profile)\b|\b(rur|profil|tube|profile)\b.*\blaser\b", "laser_tube_or_profile_cutting", 0.97),
    (r"\bciec\b.*\b(rur|profil)\b|\bsaw\b|\bpila\b", "saw_or_profile_cutting", 0.91),
    (r"\bgiec\b.*\b(blach|sheet)\b", "cnc_bending_sheet", 0.96),
    (r"\bgiec\b.*\b(rur|tube)\b", "cnc_bending_tube", 0.96),
    (r"\bgiec\b.*\b(drut|wire)\b", "cnc_bending_wire", 0.96),
    (r"\bprostow|straighten", "wire_straightening_cutting", 0.95),
    (r"\bspaw|weld\b", "mig_manual_welding", 0.8),
    (r"\brobot\b.*\bspaw|robot.*weld", "robot_welding", 0.95),
    (r"\bzgrzew|spot weld", "spot_welding", 0.95),
    (r"\bgrat|deburr|wykonc", "deburring_manual_finishing", 0.9),
    (r"\bszlif|grind", "grinding", 0.92),
    (r"\bmontaz|assembly", "assembly", 0.93),
    (r"\bpakow|packag", "packaging", 0.93),
    (r"\bprasa|pressing|stamping", "pressing", 0.9),
    (r"\bfrez|mill", "milling", 0.92),
    (r"\bwierc|drill", "drilling", 0.9),
    (r"\btocz|turning|lathe", "turning", 0.9),
    (r"\bmalow|paint", "painting", 0.9),
    (r"\bcynk|galvani", "galvanizing", 0.9),
    (r"\bsubcon|outsourc|kooperac", "subcontracting", 0.88),
    (r"\bmanual|reczn|review", "manual_review", 0.7),
]


def classify_operation(original_operation_name: str, work_center: str | None = None) -> OperationClassification:
    text = _norm(original_operation_name)
    for pattern, operation_type, confidence in _RULES:
        if re.search(pattern, text):
            return OperationClassification(
                originalOperationName=original_operation_name,
                canonicalOperationType=operation_type,
                workCenter=work_center,
                confidence=confidence,
            )

    return OperationClassification(
        originalOperationName=original_operation_name,
        canonicalOperationType="unknown_operation",
        workCenter=work_center,
        confidence=0.0,
    )
