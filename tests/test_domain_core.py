from metal_calc.costing import calculate_preliminary_cost, load_company_rates
from metal_calc.models import (
    CustomerInfo,
    FinishSpec,
    MaterialSpec,
    OperationType,
    PartSpec,
    QuantityBreak,
    RFQInput,
)
from metal_calc.routing import generate_route
from metal_calc.validators import detect_missing_information


def _valid_rfq() -> RFQInput:
    return RFQInput(
        customer=CustomerInfo(name="ACME"),
        part=PartSpec(part_name="Bracket", mass_kg=1.2),
        material=MaterialSpec(material_code="S235", thickness_mm=3.0),
        finish=FinishSpec(finish_code="painting"),
        quantity_break=QuantityBreak(quantity=100),
        requested_operations=[OperationType.LASER_CUTTING, OperationType.BENDING],
    )


def test_domain_package_imports():
    import metal_calc

    assert hasattr(metal_calc, "generate_route")


def test_basic_route_generation():
    rfq = _valid_rfq()
    route = generate_route(rfq)
    assert len(route.operations) == 2
    assert route.confidence.value >= 0.8
    assert route.risks == []


def test_missing_data_detection():
    rfq = _valid_rfq()
    rfq.part.mass_kg = None
    rfq.material.material_code = ""
    missing = detect_missing_information(rfq)
    assert "part.mass_kg" in missing.fields
    assert "material.material_code" in missing.fields


def test_cost_breakdown_model_and_values():
    rfq = _valid_rfq()
    route = generate_route(rfq)
    rates = load_company_rates()
    costs = calculate_preliminary_cost(rfq, route, rates)
    assert costs.totalEstimatedPrice > 0
    assert len(costs.assumptions) > 0
