"""
Tests for engine/calc_form.py
"""

import pytest

from metal_calc.data.routing_templates import WIRE, SHEET, MESH
from metal_calc.engine.calc_form import CalcForm
from metal_calc.engine.calculation import QuoteItem
from metal_calc.models.enums import OperationType, PriceProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wire_form(quantity: int = 100) -> CalcForm:
    form = CalcForm.from_template(WIRE, item_name="Drut fi5 S235JR", quantity=quantity)
    form.fill_operation(
        OperationType.STRAIGHTENING,
        "Prościarki do drutu",
        setup_sec=120,
        cycle_sec=2.5,
    )
    form.fill_material(
        "Drut S235JR fi5 krąg",
        unit="kg",
        quantity_net=50.0,
        scrap_factor=1.02,
        price_per_unit=4.20,
        price_source="cennik_miesięczny",
    )
    return form


# ---------------------------------------------------------------------------
# CalcForm.from_template
# ---------------------------------------------------------------------------

class TestCalcFormInit:
    def test_from_template_sets_attributes(self):
        form = CalcForm.from_template(WIRE, item_name="Test", quantity=50)
        assert form.template is WIRE
        assert form.item_name == "Test"
        assert form.quantity == 50

    def test_empty_form_has_no_operations(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=1)
        assert form.filled_op_types() == []


# ---------------------------------------------------------------------------
# fill_operation
# ---------------------------------------------------------------------------

class TestFillOperation:
    def test_fill_valid_mandatory_op(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        form.fill_operation(
            OperationType.STRAIGHTENING,
            "Prościarki do drutu",
            setup_sec=60,
            cycle_sec=1.0,
        )
        assert OperationType.STRAIGHTENING in form.filled_op_types()

    def test_fill_optional_op(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        form.fill_operation(
            OperationType.WIRE_BENDING,
            "Giętarka Montorfano",
            setup_sec=300,
            cycle_sec=5.0,
        )
        assert OperationType.WIRE_BENDING in form.filled_op_types()

    def test_fill_replaces_existing(self):
        form = _wire_form()
        form.fill_operation(
            OperationType.STRAIGHTENING,
            "Prościarki do drutu",
            setup_sec=999,
            cycle_sec=0,
        )
        summary = form.operation_summary()
        row = next(r for r in summary if r["op_type"] == OperationType.STRAIGHTENING.value)
        assert row["setup_sec"] == 999

    def test_fill_unknown_op_raises(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        with pytest.raises(ValueError, match="not defined in template"):
            form.fill_operation(
                OperationType.LASER_CUTTING,
                "Laser Fiber do blach",
                setup_sec=0,
                cycle_sec=0,
            )

    def test_fill_wrong_machine_raises(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        with pytest.raises(ValueError, match="not a candidate"):
            form.fill_operation(
                OperationType.STRAIGHTENING,
                "Robot spawalniczy Fanuc",
                setup_sec=0,
                cycle_sec=0,
            )


# ---------------------------------------------------------------------------
# fill_material
# ---------------------------------------------------------------------------

class TestFillMaterial:
    def test_single_material(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        form.fill_material("Mat A", unit="kg", quantity_net=10.0, price_per_unit=5.0)
        errors = form.validate()
        # missing mandatory op still, but material check passes
        mat_error = [e for e in errors if "material" in e.lower()]
        assert mat_error == []

    def test_multiple_materials(self):
        form = _wire_form()
        form.fill_material("Mat B", unit="szt", quantity_net=2.0, price_per_unit=12.0)
        item = form.build_quote_item()
        assert len(item.materials) == 2


# ---------------------------------------------------------------------------
# fill_outside_service
# ---------------------------------------------------------------------------

class TestFillOutsideService:
    def test_outside_service_appears_in_item(self):
        form = _wire_form()
        form.fill_outside_service(
            service_name="Cynkowanie bebn",
            service_type="cynkowanie_bebn",
            unit="kg",
            quantity=50.0,
            price_per_unit=3.80,
        )
        item = form.build_quote_item()
        assert len(item.outside_services) == 1
        assert item.outside_services[0].service_name == "Cynkowanie bebn"


# ---------------------------------------------------------------------------
# add_assumption
# ---------------------------------------------------------------------------

class TestAddAssumption:
    def test_unconfirmed_assumption_appears(self):
        form = _wire_form()
        form.add_assumption("finish", "surowe", "Klient nie podał wykończenia", confirmed=False)
        item = form.build_quote_item()
        assert item.has_unconfirmed_assumptions()

    def test_confirmed_assumption(self):
        form = _wire_form()
        form.add_assumption("finish", "ocynkowane", "Potwierdzone mailem", confirmed=True)
        item = form.build_quote_item()
        assert not item.has_unconfirmed_assumptions()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_empty_form_has_errors(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        errors = form.validate()
        assert len(errors) > 0

    def test_missing_material_is_an_error(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=60, cycle_sec=1.0,
        )
        errors = form.validate()
        assert any("material" in e.lower() for e in errors)

    def test_missing_mandatory_op_is_an_error(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=10)
        form.fill_material("Mat", unit="kg", quantity_net=1.0)
        errors = form.validate()
        assert any("mandatory" in e.lower() for e in errors)

    def test_zero_quantity_is_an_error(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=0)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=60, cycle_sec=1.0,
        )
        form.fill_material("Mat", unit="kg", quantity_net=1.0)
        errors = form.validate()
        assert any("quantity" in e.lower() for e in errors)

    def test_valid_wire_form_has_no_errors(self):
        form = _wire_form()
        assert form.validate() == []

    def test_mesh_needs_two_mandatory_ops(self):
        form = CalcForm.from_template(MESH, item_name="Siatka", quantity=200)
        form.fill_material("Drut", unit="kg", quantity_net=100.0)
        errors = form.validate()
        mandatory_errors = [e for e in errors if "mandatory" in e.lower()]
        # STRAIGHTENING + WELDING_SPOT both mandatory
        assert len(mandatory_errors) == 2


# ---------------------------------------------------------------------------
# build_quote_item
# ---------------------------------------------------------------------------

class TestBuildQuoteItem:
    def test_returns_quote_item(self):
        form = _wire_form()
        item = form.build_quote_item()
        assert isinstance(item, QuoteItem)

    def test_item_name_and_family(self):
        form = _wire_form()
        item = form.build_quote_item()
        assert item.item_name == "Drut fi5 S235JR"
        assert item.product_family == "drut"

    def test_operation_effective_time(self):
        form = _wire_form(quantity=100)
        item = form.build_quote_item()
        op = item.operations[0]
        # setup=120, cycle=2.5, qty=100 → 120 + 250 = 370
        assert op.effective_time_s() == 370.0

    def test_material_cost(self):
        form = _wire_form()
        item = form.build_quote_item()
        mat = item.materials[0]
        # qty_gross = 50 * 1.02 = 51.0; cost = 51 * 4.20 = 214.2
        assert abs(mat.cost_zl() - 214.2) < 1e-6

    def test_packaging_and_adjustment_pass_through(self):
        form = _wire_form()
        form.packaging_cost_zl = 25.0
        form.adjustment_zl = -10.0
        item = form.build_quote_item()
        assert item.packaging_cost_zl == 25.0
        assert item.adjustment_zl == -10.0


# ---------------------------------------------------------------------------
# operation_summary
# ---------------------------------------------------------------------------

class TestOperationSummary:
    def test_summary_shows_all_steps(self):
        form = _wire_form()
        summary = form.operation_summary()
        op_types = [r["op_type"] for r in summary]
        assert OperationType.STRAIGHTENING.value in op_types

    def test_unfilled_steps_have_none_times(self):
        form = _wire_form()
        summary = form.operation_summary()
        wire_bending = next(
            r for r in summary if r["op_type"] == OperationType.WIRE_BENDING.value
        )
        assert wire_bending["status"] == "unfilled"
        assert wire_bending["effective_time_s"] is None

    def test_filled_step_has_effective_time(self):
        form = _wire_form(quantity=100)
        summary = form.operation_summary()
        straight = next(
            r for r in summary if r["op_type"] == OperationType.STRAIGHTENING.value
        )
        assert straight["status"] == "filled"
        assert straight["effective_time_s"] == 370.0  # 120 + 2.5*100

    def test_unfilled_mandatory_steps_list(self):
        form = CalcForm.from_template(WIRE, item_name="X", quantity=5)
        unfilled = form.unfilled_mandatory_steps()
        assert any(s.op_type == OperationType.STRAIGHTENING for s in unfilled)

    def test_no_unfilled_mandatory_after_fill(self):
        form = _wire_form()
        assert form.unfilled_mandatory_steps() == []


# ---------------------------------------------------------------------------
# Sheet family — optional ops only added when filled
# ---------------------------------------------------------------------------

class TestSheetForm:
    def _sheet_form(self) -> CalcForm:
        form = CalcForm.from_template(SHEET, item_name="Blacha DC01 2mm", quantity=50)
        form.fill_operation(
            OperationType.LASER_CUTTING,
            "Laser Fiber do blach",
            setup_sec=300,
            cycle_sec=45.0,
        )
        form.fill_operation(
            OperationType.SHEET_BENDING,
            "Giętarka do blach SAFAN",
            setup_sec=600,
            cycle_sec=20.0,
        )
        form.fill_material(
            "Blacha DC01 2mm",
            unit="kg",
            quantity_net=80.0,
            scrap_factor=1.05,
            price_per_unit=5.50,
        )
        return form

    def test_sheet_form_valid(self):
        form = self._sheet_form()
        # NESTING is mandatory but has empty candidate_machines — cannot fill
        # so we expect one mandatory error about nesting
        errors = form.validate()
        assert any("nesting" in e.lower() for e in errors)

    def test_sheet_operations_built(self):
        form = self._sheet_form()
        item = form.build_quote_item()
        op_names = [op.operation_name for op in item.operations]
        assert "ciecie_laserem" in op_names
        assert "giecie_blachy" in op_names
