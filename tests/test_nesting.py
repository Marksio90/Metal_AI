"""
Tests for NestingResult and CalcForm.fill_nesting_result() / suggested_laser_times().
"""

import pytest

from metal_calc.data.routing_templates import SHEET, WIRE
from metal_calc.engine.calc_form import CalcForm, NestingResult
from metal_calc.models.enums import OperationType, PriceProfile

P20 = PriceProfile.MARGIN_20


def _make_nesting(
    n_sheets: int = 10,
    sheet_format: str = "2000x1000",
    cutting_time_per_sheet_s: float = 240.0,
    machine_time_per_sheet_s: float = 300.0,
    material_utilization_pct: float = 82.5,
    setup_per_batch_s: float = 300.0,
    nesting_program: str = "nest_job_001",
) -> NestingResult:
    return NestingResult(
        n_sheets=n_sheets,
        sheet_format=sheet_format,
        cutting_time_per_sheet_s=cutting_time_per_sheet_s,
        machine_time_per_sheet_s=machine_time_per_sheet_s,
        material_utilization_pct=material_utilization_pct,
        setup_per_batch_s=setup_per_batch_s,
        nesting_program=nesting_program,
    )


def _sheet_form(qty: int = 100) -> CalcForm:
    return CalcForm.from_template(SHEET, item_name="Blacha DC01 2mm", quantity=qty)


# ---------------------------------------------------------------------------
# NestingResult dataclass
# ---------------------------------------------------------------------------

class TestNestingResult:
    def test_total_machine_time(self):
        r = _make_nesting(n_sheets=10, machine_time_per_sheet_s=300.0, setup_per_batch_s=300.0)
        assert r.total_machine_time_s() == 300.0 + 10 * 300.0  # 3300

    def test_suggested_laser_setup_equals_batch_setup(self):
        r = _make_nesting(setup_per_batch_s=600.0)
        assert r.suggested_laser_setup_sec() == 600.0

    def test_suggested_laser_cycle_amortizes_over_qty(self):
        # 10 sheets × 300 s/sheet = 3000 s total / 100 pcs = 30 s/pcs
        r = _make_nesting(n_sheets=10, machine_time_per_sheet_s=300.0, setup_per_batch_s=0.0)
        assert r.suggested_laser_cycle_sec(qty=100) == 30.0

    def test_suggested_laser_cycle_qty_zero_returns_zero(self):
        r = _make_nesting()
        assert r.suggested_laser_cycle_sec(qty=0) == 0.0

    def test_effective_time_reconstruction(self):
        """OperationLine effective_time should equal total_machine_time_s."""
        n, mps, setup = 10, 300.0, 300.0
        r = _make_nesting(n_sheets=n, machine_time_per_sheet_s=mps, setup_per_batch_s=setup)
        qty = 100
        eff = r.suggested_laser_setup_sec() + r.suggested_laser_cycle_sec(qty) * qty
        assert abs(eff - r.total_machine_time_s()) < 1e-9


# ---------------------------------------------------------------------------
# CalcForm.fill_nesting_result
# ---------------------------------------------------------------------------

class TestFillNestingResult:
    def test_nesting_result_stored(self):
        form = _sheet_form()
        r = _make_nesting()
        form.fill_nesting_result(r)
        assert form._nesting_result is r

    def test_suggested_laser_times_none_before_fill(self):
        form = _sheet_form()
        assert form.suggested_laser_times() is None

    def test_suggested_laser_times_returns_dict(self):
        form = _sheet_form(qty=100)
        form.fill_nesting_result(_make_nesting())
        times = form.suggested_laser_times()
        assert times is not None
        for key in ("setup_sec", "cycle_sec", "n_sheets", "sheet_format",
                    "material_utilization_pct", "total_machine_time_s", "nesting_program"):
            assert key in times

    def test_suggested_times_values(self):
        qty = 100
        form = _sheet_form(qty=qty)
        r = _make_nesting(n_sheets=10, machine_time_per_sheet_s=300.0,
                          setup_per_batch_s=300.0)
        form.fill_nesting_result(r)
        times = form.suggested_laser_times()
        assert times["setup_sec"] == 300.0
        assert times["cycle_sec"] == 30.0   # 10×300/100
        assert times["total_machine_time_s"] == 3300.0
        assert times["n_sheets"] == 10
        assert times["material_utilization_pct"] == 82.5


# ---------------------------------------------------------------------------
# validate() — NESTING step handling
# ---------------------------------------------------------------------------

class TestValidateNestingStep:
    def test_sheet_form_without_nesting_fails_validation(self):
        form = _sheet_form()
        form.fill_material("Blacha DC01", unit="kg", quantity_net=80.0, price_per_unit=5.50)
        errors = form.validate()
        assert any("nesting" in e.lower() for e in errors)

    def test_sheet_form_with_nesting_passes_nesting_check(self):
        form = _sheet_form(qty=100)
        form.fill_nesting_result(_make_nesting())
        form.fill_material("Blacha DC01", unit="kg", quantity_net=80.0, price_per_unit=5.50)
        errors = form.validate()
        # NESTING error should be gone
        nesting_errors = [e for e in errors if "nesting" in e.lower()]
        assert nesting_errors == []

    def test_sheet_form_fully_valid_with_nesting(self):
        qty = 100
        form = _sheet_form(qty=qty)
        form.fill_nesting_result(_make_nesting(n_sheets=10, machine_time_per_sheet_s=300.0,
                                               setup_per_batch_s=300.0))
        times = form.suggested_laser_times()
        form.fill_operation(OperationType.LASER_CUTTING, "Laser Fiber do blach",
                            setup_sec=times["setup_sec"], cycle_sec=times["cycle_sec"])
        form.fill_material("Blacha DC01 2mm", unit="kg",
                           quantity_net=80.0, scrap_factor=1.05, price_per_unit=5.50)
        assert form.validate() == []

    def test_wire_form_unaffected_by_nesting_logic(self):
        """WIRE template has no machine-less mandatory steps — nesting path doesn't interfere."""
        from metal_calc.data.routing_templates import WIRE
        form = CalcForm.from_template(WIRE, item_name="Drut fi5", quantity=100)
        form.fill_operation(OperationType.STRAIGHTENING, "Prościarki do drutu",
                            setup_sec=120, cycle_sec=2.5)
        form.fill_material("Drut fi5", unit="kg", quantity_net=50.0, price_per_unit=4.20)
        assert form.validate() == []


# ---------------------------------------------------------------------------
# End-to-end: cost from nesting-derived times
# ---------------------------------------------------------------------------

class TestNestingCostCalculation:
    def test_nesting_cost_matches_formula(self):
        """
        Engine cost must equal (rate_zl_h/3600) * total_machine_time_s.

        Setup: n_sheets=10, machine_time=300s/sheet, setup=300s → total=3300s
        Laser P20 rate = 460 zł/h
        Expected cost = (460/3600) * 3300 = 421.667 zł
        """
        qty = 100
        form = _sheet_form(qty=qty)
        form.fill_nesting_result(NestingResult(
            n_sheets=10,
            sheet_format="2000x1000",
            cutting_time_per_sheet_s=240.0,
            machine_time_per_sheet_s=300.0,
            material_utilization_pct=82.5,
            setup_per_batch_s=300.0,
        ))
        times = form.suggested_laser_times()
        form.fill_operation(
            OperationType.LASER_CUTTING, "Laser Fiber do blach",
            setup_sec=times["setup_sec"], cycle_sec=times["cycle_sec"],
        )
        form.fill_material("Blacha DC01 2mm", unit="kg",
                           quantity_net=80.0, scrap_factor=1.05, price_per_unit=5.50)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        # total laser time = 300 + 10*300 = 3300 s
        expected_op_cost = (460 / 3600) * 3300
        assert abs(bd["operations_zl"] - expected_op_cost) < 0.01

    def test_material_utilization_info_preserved(self):
        """NestingResult metadata is accessible after fill_nesting_result."""
        form = _sheet_form(qty=50)
        r = NestingResult(
            n_sheets=5,
            sheet_format="3000x1500",
            cutting_time_per_sheet_s=180.0,
            machine_time_per_sheet_s=220.0,
            material_utilization_pct=76.3,
            setup_per_batch_s=180.0,
            nesting_program="job_sheet_abc",
        )
        form.fill_nesting_result(r)
        times = form.suggested_laser_times()
        assert times["material_utilization_pct"] == 76.3
        assert times["nesting_program"] == "job_sheet_abc"
        assert times["sheet_format"] == "3000x1500"
        assert times["n_sheets"] == 5
