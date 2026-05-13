from __future__ import annotations

from metal_calc.models import CostBreakdown, MachineRate, ManufacturingRoute, OperationType, RFQInput

DEFAULT_MACHINE_RATES: dict[OperationType, MachineRate] = {
    OperationType.LASER_CUTTING: MachineRate(OperationType.LASER_CUTTING, 120.0),
    OperationType.BENDING: MachineRate(OperationType.BENDING, 90.0),
    OperationType.WELDING: MachineRate(OperationType.WELDING, 110.0),
    OperationType.DEBURRING: MachineRate(OperationType.DEBURRING, 75.0),
    OperationType.PAINTING: MachineRate(OperationType.PAINTING, 80.0),
    OperationType.GALVANIZING: MachineRate(OperationType.GALVANIZING, 85.0),
    OperationType.ASSEMBLY: MachineRate(OperationType.ASSEMBLY, 95.0),
    OperationType.SUBCONTRACTING: MachineRate(OperationType.SUBCONTRACTING, 100.0),
    OperationType.MANUAL_REVIEW: MachineRate(OperationType.MANUAL_REVIEW, 60.0),
}


def estimate_cost(rfq: RFQInput, route: ManufacturingRoute) -> CostBreakdown:
    qty = max(rfq.quantity_break.quantity, 0)
    material_cost = (rfq.part.mass_kg or 0.0) * qty * 2.5
    operation_cost = sum(DEFAULT_MACHINE_RATES[op.operation].hourly_rate * 0.1 for op in route.operations)
    finishing_cost = 15.0 if rfq.finish.finish_code not in {"unknown_finish", "raw"} else 0.0
    subcontracting_cost = 25.0 if any(op.operation == OperationType.SUBCONTRACTING for op in route.operations) else 0.0
    total = material_cost + operation_cost + finishing_cost + subcontracting_cost
    return CostBreakdown(
        material_cost=round(material_cost, 2),
        operation_cost=round(operation_cost, 2),
        finishing_cost=round(finishing_cost, 2),
        subcontracting_cost=round(subcontracting_cost, 2),
        total_cost=round(total, 2),
        assumptions=["Machine time baseline: 0.1h per operation per RFQ."],
    )
