"""
Tests for RFQ completeness check.

Covers:
  - all critical fields present → READY_FOR_CALC
  - missing critical field → MISSING_DATA
  - family-specific fields checked
  - advisory fields don't block
  - invalid quantity → MISSING_DATA
  - nieokreślone finish → warning only
"""

import pytest

from metal_calc.engine.rfq_intake import (
    check_rfq_completeness,
    build_missing_data_reply,
)
from metal_calc.models.enums import RFQStatus, ProductFamily


def _base_wire() -> dict:
    return {
        "client": "Klient ABC",
        "quantity": 200,
        "product_family": ProductFamily.WIRE.value,
        "material_family": "stal_czarna",
        "material_grade": "S235JR",
        "finish": "malowanie_proszkowe",
        "wire_diameter_mm": 4.0,
        "unit_mass_kg": 0.05,
    }


def _base_sheet() -> dict:
    return {
        "client": "Klient ABC",
        "quantity": 50,
        "product_family": ProductFamily.SHEET.value,
        "material_family": "stal_czarna",
        "material_grade": "DC01",
        "finish": "surowe",
        "thickness_mm": 2.0,
        "unit_mass_kg": 0.8,
        "nesting_sheets_count": 5,
    }


class TestReadyForCalc:
    def test_complete_wire_rfq(self):
        result = check_rfq_completeness(_base_wire())
        assert result.status == RFQStatus.READY_FOR_CALC
        assert result.ready_for_calculation
        assert result.missing_critical == []

    def test_complete_sheet_rfq(self):
        result = check_rfq_completeness(_base_sheet())
        assert result.status == RFQStatus.READY_FOR_CALC

    def test_complete_tube_rfq(self):
        data = {
            "client": "X",
            "quantity": 100,
            "product_family": ProductFamily.TUBE.value,
            "material_family": "stal_czarna",
            "material_grade": "S235JR",
            "finish": "cynkowanie",
            "tube_od_mm": 20.0,
            "wall_thickness_mm": 1.5,
            "length_mm": 500.0,
            "unit_mass_kg": 0.3,
        }
        result = check_rfq_completeness(data)
        assert result.status == RFQStatus.READY_FOR_CALC

    def test_complete_mesh_rfq(self):
        data = {
            "client": "X",
            "quantity": 1000,
            "product_family": ProductFamily.MESH.value,
            "material_family": "stal_czarna",
            "material_grade": "S235JR",
            "finish": "surowe",
            "wire_diameter_mm": 3.0,
            "mesh_width_mm": 400.0,
            "mesh_height_mm": 600.0,
            "unit_mass_kg": 0.4,
        }
        result = check_rfq_completeness(data)
        assert result.status == RFQStatus.READY_FOR_CALC

    def test_complete_structure_rfq(self):
        data = {
            "client": "X",
            "quantity": 10,
            "product_family": ProductFamily.STRUCTURE.value,
            "material_family": "stal_czarna",
            "material_grade": "S235JR",
            "finish": "malowanie_proszkowe",
            "component_list": ["detal_A", "detal_B"],
            "assembly_description": "Spawanie 4 elementów",
        }
        result = check_rfq_completeness(data)
        assert result.status == RFQStatus.READY_FOR_CALC


class TestMissingData:
    def test_missing_client(self):
        data = _base_wire()
        del data["client"]
        result = check_rfq_completeness(data)
        assert result.status == RFQStatus.MISSING_DATA
        assert "client" in result.missing_critical

    def test_missing_quantity(self):
        data = _base_wire()
        del data["quantity"]
        result = check_rfq_completeness(data)
        assert "quantity" in result.missing_critical

    def test_missing_material_grade(self):
        data = _base_wire()
        del data["material_grade"]
        result = check_rfq_completeness(data)
        assert "material_grade" in result.missing_critical

    def test_missing_finish(self):
        data = _base_wire()
        del data["finish"]
        result = check_rfq_completeness(data)
        assert "finish" in result.missing_critical

    def test_missing_wire_diameter(self):
        data = _base_wire()
        del data["wire_diameter_mm"]
        result = check_rfq_completeness(data)
        assert "wire_diameter_mm" in result.missing_critical

    def test_missing_nesting_sheets(self):
        data = _base_sheet()
        del data["nesting_sheets_count"]
        result = check_rfq_completeness(data)
        assert "nesting_sheets_count" in result.missing_critical

    def test_zero_quantity(self):
        data = _base_wire()
        data["quantity"] = 0
        result = check_rfq_completeness(data)
        assert result.status == RFQStatus.MISSING_DATA
        assert "quantity_must_be_positive" in result.missing_critical

    def test_negative_quantity(self):
        data = _base_wire()
        data["quantity"] = -5
        result = check_rfq_completeness(data)
        assert "quantity_must_be_positive" in result.missing_critical

    def test_string_quantity(self):
        data = _base_wire()
        data["quantity"] = "dużo"
        result = check_rfq_completeness(data)
        assert "quantity_must_be_numeric" in result.missing_critical

    def test_empty_string_client(self):
        data = _base_wire()
        data["client"] = "   "
        result = check_rfq_completeness(data)
        assert "client" in result.missing_critical

    def test_empty_list_component(self):
        data = {
            "client": "X",
            "quantity": 5,
            "product_family": ProductFamily.STRUCTURE.value,
            "material_family": "stal_czarna",
            "material_grade": "S235JR",
            "finish": "malowanie",
            "component_list": [],
            "assembly_description": "...",
        }
        result = check_rfq_completeness(data)
        assert "component_list" in result.missing_critical


class TestAdvisoryAndWarnings:
    def test_missing_salesperson_is_advisory_not_critical(self):
        data = _base_wire()
        result = check_rfq_completeness(data)
        assert "salesperson" in result.missing_advisory
        assert result.status == RFQStatus.READY_FOR_CALC

    def test_nieokreslone_finish_is_warning(self):
        data = _base_wire()
        data["finish"] = "nieokreślone"
        result = check_rfq_completeness(data)
        assert result.status == RFQStatus.READY_FOR_CALC
        assert any("nieokreślone" in w for w in result.warnings)

    def test_unknown_family_warning(self):
        data = _base_wire()
        data["product_family"] = "nieznany_typ"
        result = check_rfq_completeness(data)
        assert any("family-specific checks skipped" in w for w in result.warnings)


class TestMissingDataReply:
    def test_reply_contains_rfq_number(self):
        data = _base_wire()
        del data["quantity"]
        result = check_rfq_completeness(data)
        reply = build_missing_data_reply("RFQ-2025-042", "Klient ABC", result)
        assert "RFQ-2025-042" in reply
        assert "Ilość sztuk" in reply

    def test_reply_references_missing_fields(self):
        data = _base_sheet()
        del data["thickness_mm"]
        del data["nesting_sheets_count"]
        result = check_rfq_completeness(data)
        reply = build_missing_data_reply("RFQ-001", "X", result)
        assert "Grubość blachy" in reply
        assert "nesting" in reply.lower() or "Liczba arkuszy" in reply
