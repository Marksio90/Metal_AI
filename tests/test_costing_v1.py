from metal_calc.costing import calculate_preliminary_cost, load_company_rates
from metal_calc.models import CustomerInfo, FinishSpec, MaterialSpec, OperationType, PartSpec, QuantityBreak, RFQInput
from metal_calc.routing import generate_route


def _rfq() -> RFQInput:
    return RFQInput(
        customer=CustomerInfo(name="ACME"),
        part=PartSpec(part_name="P1", mass_kg=2.0),
        material=MaterialSpec(material_code="s235", thickness_mm=3.0),
        finish=FinishSpec(finish_code="painting"),
        quantity_break=QuantityBreak(quantity=10),
        requested_operations=[OperationType.LASER_CUTTING, OperationType.BENDING],
    )


def test_operation_setup_markup_risk_buffer():
    rates = load_company_rates()
    rfq = _rfq()
    route = generate_route(rfq)
    result = calculate_preliminary_cost(rfq, route, rates)
    assert result.operationCost == 43.0
    assert result.setupCost == 122.5
    assert result.riskBufferValue > 0
    assert result.markupValue > 0
    assert result.totalEstimatedPrice > result.subtotalBeforeBuffers


def test_assumptions_and_warnings_present():
    rates = load_company_rates()
    rfq = _rfq()
    route = generate_route(rfq)
    result = calculate_preliminary_cost(rfq, route, rates)
    assert len(result.assumptions) >= 3
    assert isinstance(result.warnings, list)
