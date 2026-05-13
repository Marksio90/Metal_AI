from __future__ import annotations

from metal_calc.models import OperationType

SUPPORTED_OPERATIONS = {
    OperationType.LASER_CUTTING,
    OperationType.BENDING,
    OperationType.WELDING,
    OperationType.DEBURRING,
    OperationType.PAINTING,
    OperationType.GALVANIZING,
    OperationType.ASSEMBLY,
    OperationType.SUBCONTRACTING,
    OperationType.MANUAL_REVIEW,
}
