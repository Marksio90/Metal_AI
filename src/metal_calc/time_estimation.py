"""Operation time estimation based on anonymized historical baselines."""

from __future__ import annotations

from copy import deepcopy

from metal_calc.knowledge import OPERATION_TIME_BASELINES, get_preferred_work_centers


def _confidence_from_sample_count(sample_count: int) -> str:
    if sample_count >= 50:
        return "high"
    if 10 <= sample_count <= 49:
        return "medium"
    if 3 <= sample_count <= 9:
        return "low"
    return "insufficient"


class OperationTimeEstimator:
    """Estimator that uses baseline priors and supports feedback updates."""

    def __init__(self, baseline_rows: list[dict] | None = None) -> None:
        rows = baseline_rows if baseline_rows is not None else OPERATION_TIME_BASELINES
        self._rows = deepcopy(rows)

    def estimate(
        self,
        operation_type: str,
        work_center: str | None = None,
        manual_override_seconds: float | None = None,
    ) -> dict:
        if manual_override_seconds is not None:
            return {
                "operationType": operation_type,
                "workCenter": work_center,
                "estimatedSeconds": manual_override_seconds,
                "timeRangeSeconds": None,
                "sampleCount": None,
                "confidence": "manual_override",
                "source": "manual_override",
                "requiresHumanReview": False,
            }

        baseline = self._find_best_baseline(operation_type, work_center)
        if baseline is None:
            return {
                "operationType": operation_type,
                "workCenter": work_center,
                "estimatedSeconds": None,
                "timeRangeSeconds": None,
                "sampleCount": 0,
                "confidence": "insufficient",
                "source": "no_historical_baseline",
                "requiresHumanReview": True,
            }

        sample_count = baseline["sampleCount"]
        confidence = _confidence_from_sample_count(sample_count)

        return {
            "operationType": operation_type,
            "workCenter": baseline["workCenter"],
            "estimatedSeconds": baseline["medianSeconds"],
            "timeRangeSeconds": {
                "min": baseline["minSeconds"],
                "median": baseline["medianSeconds"],
                "average": baseline["averageSeconds"],
                "max": baseline["maxSeconds"],
            },
            "sampleCount": sample_count,
            "confidence": confidence,
            "source": baseline["source"],
            "requiresHumanReview": confidence in {"low", "insufficient"},
        }

    def apply_feedback(
        self,
        operation_type: str,
        actual_seconds: float,
        work_center: str | None = None,
    ) -> dict:
        baseline = self._find_best_baseline(operation_type, work_center)

        if baseline is None:
            new_baseline = {
                "operationType": operation_type,
                "workCenter": work_center or "UNKNOWN",
                "sampleCount": 1,
                "medianSeconds": actual_seconds,
                "averageSeconds": actual_seconds,
                "minSeconds": actual_seconds,
                "maxSeconds": actual_seconds,
                "source": "anonymized_historical_excel_baseline_with_feedback",
            }
            self._rows.append(new_baseline)
            return new_baseline

        previous_count = baseline["sampleCount"]
        new_count = previous_count + 1
        previous_avg = baseline["averageSeconds"]
        new_avg = ((previous_avg * previous_count) + actual_seconds) / new_count

        baseline["sampleCount"] = new_count
        baseline["averageSeconds"] = new_avg
        baseline["minSeconds"] = min(baseline["minSeconds"], actual_seconds)
        baseline["maxSeconds"] = max(baseline["maxSeconds"], actual_seconds)
        baseline["source"] = "anonymized_historical_excel_baseline_with_feedback"
        return baseline

    def _find_best_baseline(self, operation_type: str, work_center: str | None = None) -> dict | None:
        candidates = [row for row in self._rows if row["operationType"] == operation_type]
        if not candidates:
            return None

        if work_center:
            for row in candidates:
                if row["workCenter"] == work_center:
                    return row

        preferred_work_centers = get_preferred_work_centers(operation_type)
        for preferred in preferred_work_centers:
            for row in candidates:
                if row["workCenter"] == preferred:
                    return row

        return sorted(candidates, key=lambda row: row["sampleCount"], reverse=True)[0]
