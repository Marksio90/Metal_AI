from __future__ import annotations

from metal_calc.time_estimation import OperationTimeEstimator


def test_estimate_uses_historical_median_and_range() -> None:
    est = OperationTimeEstimator()
    result = est.estimate("laser_sheet_cutting", "LASER")
    assert result["estimatedSeconds"] == 24.0
    assert result["timeRangeSeconds"]["min"] == 4.0
    assert result["timeRangeSeconds"]["max"] == 1000.0
    assert result["sampleCount"] == 245
    assert result["confidence"] == "high"


def test_estimate_missing_baseline_requires_human_review() -> None:
    est = OperationTimeEstimator()
    result = est.estimate("non_existing_operation", None)
    assert result["estimatedSeconds"] is None
    assert result["confidence"] == "insufficient"
    assert result["requiresHumanReview"] is True
