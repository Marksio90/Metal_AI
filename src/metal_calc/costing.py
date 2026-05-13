from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from metal_calc.models import ManufacturingRoute, RFQInput


@dataclass(slots=True)
class PreliminaryCostResult:
    currency: str
    materialCost: float
    operationCost: float
    setupCost: float
    finishingCost: float
    subtotalBeforeBuffers: float
    riskBufferValue: float
    markupValue: float
    totalEstimatedPrice: float
    assumptions: list[str]
    warnings: list[str]


def load_company_rates(path: str = "config/company_rates.example.json") -> dict:
    return json.loads(Path(path).read_text())


def calculate_preliminary_cost(rfq: RFQInput, route: ManufacturingRoute, rates: dict) -> PreliminaryCostResult:
    warnings: list[str] = []
    assumptions = [
        "Material cost is placeholder baseline (mass * qty * 2.5).",
        "Finishing cost is placeholder flat value based on finish availability.",
        "Estimate is preliminary and not final quotation.",
    ]

    qty = max(rfq.quantity_break.quantity, 0)
    material_cost = (rfq.part.mass_kg or 0.0) * qty * 2.5

    machine_rates = rates.get("machineRates", {})
    setup_times = rates.get("setupTimesMinutes", {})

    operation_cost = 0.0
    setup_cost = 0.0
    for op in route.operations:
        op_key = op.operation.value
        rate = float(machine_rates.get(op_key, 0.0))
        if rate == 0.0:
            warnings.append(f"Missing machine rate for operation: {op_key}")
        operation_cost += rate * 0.1

        setup_minutes = float(setup_times.get(op_key, 0.0))
        setup_cost += (setup_minutes / 60.0) * rate

    finishing_cost = 30.0 if rfq.finish.finish_code not in {"unknown_finish", "raw"} else 0.0
    subtotal = material_cost + operation_cost + setup_cost + finishing_cost

    risk_buffer_percent = float(rates.get("riskBufferPercent", 0.0))
    markup_percent = float(rates.get("markupPercent", 0.0))
    risk_buffer_value = subtotal * (risk_buffer_percent / 100.0)
    markup_value = (subtotal + risk_buffer_value) * (markup_percent / 100.0)
    total = subtotal + risk_buffer_value + markup_value

    return PreliminaryCostResult(
        currency=rates.get("currency", "PLN"),
        materialCost=round(material_cost, 2),
        operationCost=round(operation_cost, 2),
        setupCost=round(setup_cost, 2),
        finishingCost=round(finishing_cost, 2),
        subtotalBeforeBuffers=round(subtotal, 2),
        riskBufferValue=round(risk_buffer_value, 2),
        markupValue=round(markup_value, 2),
        totalEstimatedPrice=round(total, 2),
        assumptions=assumptions,
        warnings=warnings,
    )
