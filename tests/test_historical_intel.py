from __future__ import annotations

import types

from metal_calc.costing import OperationCostInput, calculate_deterministic_cost
from metal_calc.importers.legacy_excel.anonymizer import anonymize_filename
from metal_calc.importers.legacy_excel.normalizer import normalize_rows
from metal_calc.importers.legacy_excel.parser import parse_legacy_excel
from metal_calc.importers.legacy_excel.schema import RawOperationRow
from metal_calc.knowledge import (
    CANONICAL_OPERATION_TYPES,
    OPERATION_TIME_BASELINES,
    classify_operation,
    get_preferred_work_centers,
)
from metal_calc.routing import suggest_route_from_context
from metal_calc.time_estimation import OperationTimeEstimator
from metal_calc.validators import detect_missing_information
from metal_calc.models import CustomerInfo, FinishSpec, MaterialSpec, PartSpec, QuantityBreak, RFQInput


def test_operation_taxonomy_and_mapping() -> None:
    assert "laser_sheet_cutting" in CANONICAL_OPERATION_TYPES
    cls = classify_operation("Ciąć Blachę CNC Laser", "LASER")
    assert cls.canonicalOperationType == "laser_sheet_cutting"
    assert cls.originalOperationName == "Ciąć Blachę CNC Laser"


def test_work_center_mapping_and_baseline_loading() -> None:
    pref = get_preferred_work_centers("cnc_bending_sheet")
    assert pref[0] == "GIĘTARKA SAFAN"
    laser = [r for r in OPERATION_TIME_BASELINES if r["operationType"] == "laser_sheet_cutting" and r["workCenter"] == "LASER"][0]
    assert laser["medianSeconds"] == 24.0


def test_time_estimate_confidence_and_batch_quantity_formula() -> None:
    est = OperationTimeEstimator()
    high = est.estimate("laser_sheet_cutting", "LASER")
    assert high["confidence"] == "high"
    low = est.estimate("milling", "NARZĘDZIOWNIA HAAS")
    assert low["confidence"] == "low"


def test_operation_cost_formula_and_batch_time() -> None:
    op = OperationCostInput(
        operationType="laser_sheet_cutting",
        quantity=10,
        timePerPieceSeconds=24,
        setupTimeSeconds=120,
        laborRatePerHour=100,
        laborMarkup=0.2,
        departmentOverheadFactor=0.1,
        generalOverheadFactor=0.05,
        workCenter="LASER",
    )
    result = calculate_deterministic_cost(
        currency="PLN",
        material_cost=100,
        material_procurement_markup=0,
        operations=[op],
        finishing_cost=0,
        packaging_cost=0,
        subcontracting_cost=0,
        special_costs=0,
        risk_buffer=0,
        sales_markup_percent=0,
    )
    assert result.operationCosts[0]["timeSeconds"]["total"] == 360
    assert round(result.operationCosts[0]["operationHours"], 4) == 0.1
    assert round(result.operationCosts[0]["directLaborCost"], 2) == 12.0


def test_rfq_route_suggestion_and_missing_detection() -> None:
    route = suggest_route_from_context(
        rfq_text="sheet metal laser bending powder coating",
        material_type="sheet",
        geometry_hints=["flat"],
        finish_type="powder",
        shippable=True,
    )
    types = [r["operationType"] for r in route]
    assert "laser_sheet_cutting" in types
    assert "cnc_bending_sheet" in types
    assert "packaging" in types

    rfq = RFQInput(
        customer=CustomerInfo(name="A"),
        part=PartSpec(part_name="p"),
        material=MaterialSpec(material_code="unknown_material", thickness_mm=None),
        finish=FinishSpec(finish_code="unknown_finish"),
        quantity_break=QuantityBreak(quantity=0),
    )
    missing = detect_missing_information(rfq)
    assert missing.fields


def test_legacy_importer_parser_and_anonymizer_with_synthetic_workbook(monkeypatch) -> None:
    class FakeSheet:
        def __init__(self, rows):
            self._rows = rows

        def __getitem__(self, key):
            if key == 1:
                return [types.SimpleNamespace(value=v) for v in self._rows[0]]
            raise KeyError

        def iter_rows(self, min_row=2, values_only=True):
            for r in self._rows[min_row - 1 :]:
                yield tuple(r)

    class FakeWorkbook:
        sheetnames = ["GLOWNA", "ROB_MAT", "Pakowanie"]

        def __getitem__(self, item):
            rows = [
                ["operacja", "brygada", "time_seconds", "setup_seconds", "rate", "overhead"],
                ["Ciąć Blachę CNC Laser", "LASER", 24.0, 120.0, 1, 1],
                ["Material line", "", "", "", "", ""],
                ["Pakowanie", "PAKOWANIE", 10.0, 0.0, 1, 1],
            ]
            return FakeSheet(rows)

    fake_module = types.SimpleNamespace(load_workbook=lambda filename, data_only: FakeWorkbook())
    monkeypatch.setitem(__import__("sys").modules, "openpyxl", fake_module)

    parsed = parse_legacy_excel("private_file.xlsx")
    assert parsed["detectedSheets"] == ["GLOWNA", "ROB_MAT", "Pakowanie"]
    assert parsed["operations"]

    normalized, issues = normalize_rows(
        source_filename=parsed["sourceFile"],
        rows=parsed["operations"],
        material_detected=parsed["materialDetected"],
        packaging_detected=parsed["packagingDetected"],
        cost_summary_detected=parsed["costSummaryDetected"],
    )
    assert issues == []
    assert normalized[0].source.startswith("anon_")
    assert anonymize_filename("private_file.xlsx").startswith("anon_")


def test_no_sensitive_data_in_synthetic_fixture() -> None:
    import json
    from pathlib import Path

    fixture = Path("src/metal_calc/importers/legacy_excel/fixtures/synthetic_legacy_import_output.json")
    data = json.loads(fixture.read_text())
    dumped = json.dumps(data).lower()
    blocked = ["customer", "drawing", "final price", "company rate", ".xlsx"]
    assert not any(token in dumped for token in blocked)
