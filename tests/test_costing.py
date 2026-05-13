from __future__ import annotations

from metal_calc.costing import OperationCostInput, calculate_deterministic_cost


def test_operation_to_cost_formula_chain() -> None:
    result = calculate_deterministic_cost(
        currency="PLN",
        material_cost=50.0,
        material_procurement_markup=5.0,
        operations=[
            OperationCostInput(
                operationType="laser_sheet_cutting",
                quantity=10,
                timePerPieceSeconds=24.0,
                setupTimeSeconds=120.0,
                laborRatePerHour=100.0,
                laborMarkup=0.2,
                departmentOverheadFactor=0.1,
                generalOverheadFactor=0.05,
                workCenter="LASER",
            )
        ],
        finishing_cost=10.0,
        packaging_cost=5.0,
        subcontracting_cost=0.0,
        special_costs=0.0,
        risk_buffer=5.0,
        sales_markup_percent=0.1,
    )

    op = result.operationCosts[0]
    assert round(op["operationHours"], 3) == 0.1
    assert round(op["directLaborCost"], 2) == 12.0
    assert round(op["departmentOverheadCost"], 2) == 1.2
    assert round(op["generalOverheadCost"], 2) == 0.6
    assert round(op["operationTotalCost"], 2) == 13.8


def test_batch_quantity_time_formula() -> None:
    result = calculate_deterministic_cost(
        currency="PLN",
        material_cost=0.0,
        material_procurement_markup=0.0,
        operations=[
            OperationCostInput(
                operationType="cnc_bending_sheet",
                quantity=100,
                timePerPieceSeconds=60.0,
                setupTimeSeconds=600.0,
                laborRatePerHour=60.0,
                laborMarkup=0.0,
                departmentOverheadFactor=0.0,
                generalOverheadFactor=0.0,
            )
        ],
        finishing_cost=0.0,
        packaging_cost=0.0,
        subcontracting_cost=0.0,
        special_costs=0.0,
        risk_buffer=0.0,
        sales_markup_percent=0.0,
    )
    op = result.operationCosts[0]
    assert op["timeSeconds"]["total"] == 6600.0
    assert round(op["operationHours"], 4) == round(6600.0 / 3600.0, 4)
