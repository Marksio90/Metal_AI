from __future__ import annotations

from metal_calc.knowledge import KNOWN_WORK_CENTERS, PREFERRED_WORK_CENTERS_BY_OPERATION_TYPE


def list_known_work_centers() -> list[str]:
    return list(KNOWN_WORK_CENTERS)


def get_work_centers_for_operation(operation_type: str) -> list[str]:
    return list(PREFERRED_WORK_CENTERS_BY_OPERATION_TYPE.get(operation_type, []))
