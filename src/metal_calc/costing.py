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


@dataclass(slots=True)
class OperationCostInput:
    operationType: str
    quantity: int
    timePerPieceSeconds: float
    setupTimeSeconds: float
    laborRatePerHour: float
    laborMarkup: float
    departmentOverheadFactor: float
    generalOverheadFactor: float
    workCenter: str | None = None


@dataclass(slots=True)
class DeterministicCostResult:
    assumptions: list[str]
    missingData: list[str]
    operationCosts: list[dict]
    materialCosts: dict
    packagingCosts: dict
    finishingCosts: dict
    riskBuffer: dict
    margin: dict
    confidence: str
    requiresHumanReview: bool
    productionCost: float
    priceBeforeMargin: float
    sellingPrice: float
    finalPrice: float


def load_company_rates(path: str = "config/company_rates.example.json") -> dict:
    return json.loads(Path(path).read_text())


def calculate_operation_cost(operation: OperationCostInput) -> dict:
    total_operation_time_seconds = operation.setupTimeSeconds + (operation.timePerPieceSeconds * operation.quantity)
    operation_hours = total_operation_time_seconds / 3600.0

    direct_labor_cost = operation_hours * operation.laborRatePerHour * (1.0 + operation.laborMarkup)
    department_overhead_cost = direct_labor_cost * operation.departmentOverheadFactor
    general_overhead_cost = direct_labor_cost * operation.generalOverheadFactor
    operation_total_cost = direct_labor_cost + department_overhead_cost + general_overhead_cost

    return {
        "operationType": operation.operationType,
        "workCenter": operation.workCenter,
        "quantity": operation.quantity,
        "timeSeconds": {
            "setup": operation.setupTimeSeconds,
            "perPiece": operation.timePerPieceSeconds,
            "total": total_operation_time_seconds,
        },
        "operationHours": operation_hours,
        "directLaborCost": direct_labor_cost,
        "departmentOverheadCost": department_overhead_cost,
        "generalOverheadCost": general_overhead_cost,
        "operationTotalCost": operation_total_cost,
    }


def calculate_deterministic_cost(
    *,
    currency: str,
    material_cost: float,
    material_procurement_markup: float,
    operations: list[OperationCostInput],
    finishing_cost: float,
    packaging_cost: float,
    subcontracting_cost: float,
    special_costs: float,
    risk_buffer: float,
    sales_markup_percent: float,
    rounding_digits: int = 2,
) -> DeterministicCostResult:
    assumptions = [
        "Costing is deterministic and formula-based (not generated from LLM free text).",
        "Operation cost = direct labor + department overhead + general overhead.",
        "Selling price = (production cost + risk buffer) × (1 + sales markup).",
    ]
    missing_data: list[str] = []

    operation_cost_rows = []
    for operation in operations:
        if operation.laborRatePerHour <= 0:
            missing_data.append(f"Missing/invalid labor rate for {operation.operationType}")
        if operation.timePerPieceSeconds < 0 or operation.setupTimeSeconds < 0:
            missing_data.append(f"Negative time input for {operation.operationType}")
        operation_cost_rows.append(calculate_operation_cost(operation))

    total_operation_cost = sum(row["operationTotalCost"] for row in operation_cost_rows)

    production_cost = (
        material_cost
        + material_procurement_markup
        + total_operation_cost
        + finishing_cost
        + packaging_cost
        + subcontracting_cost
        + special_costs
    )
    price_before_margin = production_cost + risk_buffer
    selling_price = price_before_margin * (1.0 + sales_markup_percent)
    final_price = round(selling_price, rounding_digits)

    confidence = "high" if not missing_data else "medium"
    requires_human_review = bool(missing_data)

    return DeterministicCostResult(
        assumptions=assumptions,
        missingData=missing_data,
        operationCosts=operation_cost_rows,
        materialCosts={
            "materialCost": material_cost,
            "materialProcurementMarkup": material_procurement_markup,
            "currency": currency,
        },
        packagingCosts={"packagingCost": packaging_cost, "currency": currency},
        finishingCosts={"finishingCost": finishing_cost, "currency": currency},
        riskBuffer={"riskBuffer": risk_buffer, "currency": currency},
        margin={"salesMarkupPercent": sales_markup_percent, "currency": currency},
        confidence=confidence,
        requiresHumanReview=requires_human_review,
        productionCost=production_cost,
        priceBeforeMargin=price_before_margin,
        sellingPrice=selling_price,
        finalPrice=final_price,
    )


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
