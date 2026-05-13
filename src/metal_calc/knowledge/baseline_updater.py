"""Persistent feedback integration for OperationTimeEstimator.

Reads EstimatorFeedback rows from the database and applies human corrections
to a fresh OperationTimeEstimator instance. Call this at application startup
to ensure time estimates reflect accumulated estimator corrections.

The import of app.persistence_models is deferred to runtime to avoid a hard
dependency from the metal_calc library on the FastAPI application layer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from metal_calc.time_estimation import OperationTimeEstimator

_log = logging.getLogger("metal_calc.knowledge.baseline_updater")

# Placeholder hourly rate used to convert corrected PLN cost → estimated seconds.
# Replace with actual work-center rate lookup when rate tables are available via API.
_DEFAULT_RATE_PLN_PER_HOUR = 100.0


def build_estimator_from_feedback(db: "Session") -> OperationTimeEstimator:
    """Create an OperationTimeEstimator pre-loaded with persisted human corrections.

    Reads all EstimatorFeedback records that contain a corrected operation route
    and a corrected cost, then applies them to the estimator's in-memory baselines.

    Returns a new OperationTimeEstimator; the caller should cache this instance
    (e.g., as a module-level singleton refreshed at startup).
    """
    # Deferred import keeps metal_calc independent of the app layer.
    try:
        from app.persistence_models import EstimatorFeedback  # type: ignore[import]
    except ImportError:
        _log.warning("app.persistence_models not available — returning default estimator.")
        return OperationTimeEstimator()

    estimator = OperationTimeEstimator()

    rows = (
        db.query(EstimatorFeedback)
        .filter(
            EstimatorFeedback.corrected_operation_route.isnot(None),
            EstimatorFeedback.corrected_cost.isnot(None),
        )
        .order_by(EstimatorFeedback.id.asc())
        .all()
    )

    applied = 0
    for row in rows:
        route = (row.corrected_operation_route or {}).get("route", [])
        if not route or not row.corrected_cost:
            continue
        cost_per_op = row.corrected_cost / len(route)
        estimated_seconds = (cost_per_op / _DEFAULT_RATE_PLN_PER_HOUR) * 3600.0
        for op_name in route:
            estimator.apply_feedback(
                operation_type=op_name,
                actual_seconds=estimated_seconds,
            )
            applied += 1

    _log.info("BaselineUpdater: applied %d operation feedback entries from DB.", applied)
    return estimator
