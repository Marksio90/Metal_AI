"""Deterministic RFQ risk rule evaluation.

This module intentionally avoids LLM-based judgement and provides stable,
auditable heuristics for early estimator attention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RiskFlag:
    code: str
    severity: str
    message: str


def evaluate_rfq_risk_flags(data: dict[str, Any]) -> list[RiskFlag]:
    """Return deterministic risk flags based on RFQ payload values."""
    flags: list[RiskFlag] = []

    qty = data.get("quantity")
    if isinstance(qty, int) and qty >= 10000:
        flags.append(
            RiskFlag(
                code="HIGH_VOLUME_ORDER",
                severity="medium",
                message="High quantity order may require capacity and lead-time validation.",
            )
        )

    finish = data.get("finish")
    if isinstance(finish, str) and finish.strip().lower() in {"nieokreślone", "unknown"}:
        flags.append(
            RiskFlag(
                code="UNSPECIFIED_FINISH",
                severity="high",
                message="Finish/coating not specified, external process cost may be inaccurate.",
            )
        )

    if data.get("product_family") == "structure":
        components = data.get("component_list")
        if isinstance(components, list) and len(components) >= 20:
            flags.append(
                RiskFlag(
                    code="LARGE_ASSEMBLY_SCOPE",
                    severity="medium",
                    message="Large component list detected; validate assembly labor and sequencing.",
                )
            )

    return flags
