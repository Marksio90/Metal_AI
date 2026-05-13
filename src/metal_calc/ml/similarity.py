"""Cosine-similarity search over historical quote items.

Feature vector (6 dimensions, all normalized to [0, 1]):
  [product_family_rank, material_family_rank, thickness_mm_norm,
   unit_mass_kg_norm, quantity_log_norm, operation_count_norm]

Pure Python implementation — no numpy or scikit-learn dependency required.
Suitable for up to ~10 000 historical items; for larger sets use a vector DB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class HistoricalQuoteFeatures:
    rfq_id: str
    product_family: str | None = None
    material_family: str | None = None
    thickness_mm: float | None = None
    unit_mass_kg: float | None = None
    quantity: int | None = None
    operation_types: list[str] = field(default_factory=list)
    final_price_zl: float | None = None
    final_margin_pct: float | None = None
    decision: str | None = None


def _feature_vector(
    item: HistoricalQuoteFeatures,
    families: list[str],
    materials: list[str],
) -> list[float]:
    """Map a quote item to a normalized 6-dimensional float vector."""
    max_fam = max(len(families) - 1, 1)
    max_mat = max(len(materials) - 1, 1)

    pf = families.index(item.product_family) / max_fam if item.product_family in families else 0.0
    mf = materials.index(item.material_family) / max_mat if item.material_family in materials else 0.0
    th = min((item.thickness_mm or 0.0) / 50.0, 1.0)        # cap at 50 mm
    um = min((item.unit_mass_kg or 0.0) / 100.0, 1.0)        # cap at 100 kg
    qt = math.log1p(item.quantity or 0) / math.log1p(10_000)  # log scale, cap at 10k
    op = min(len(item.operation_types) / 10.0, 1.0)           # cap at 10 operations
    return [pf, mf, th, um, qt, op]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_similar_quotes(
    query: HistoricalQuoteFeatures,
    candidates: Sequence[HistoricalQuoteFeatures],
    top_k: int = 5,
) -> list[dict]:
    """Return the top-k most similar historical quotes with similarity scores.

    Returns a list of dicts, each containing:
      rfq_id, similarity_score, final_price_zl, final_margin_pct,
      decision, product_family, material_family, quantity
    """
    if not candidates:
        return []

    all_families = sorted({c.product_family for c in candidates if c.product_family})
    all_materials = sorted({c.material_family for c in candidates if c.material_family})

    query_vec = _feature_vector(query, all_families, all_materials)

    scored = []
    for candidate in candidates:
        cand_vec = _feature_vector(candidate, all_families, all_materials)
        score = _cosine_similarity(query_vec, cand_vec)
        scored.append({
            "rfq_id": candidate.rfq_id,
            "similarity_score": round(score, 4),
            "final_price_zl": candidate.final_price_zl,
            "final_margin_pct": candidate.final_margin_pct,
            "decision": candidate.decision,
            "product_family": candidate.product_family,
            "material_family": candidate.material_family,
            "quantity": candidate.quantity,
        })

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]
