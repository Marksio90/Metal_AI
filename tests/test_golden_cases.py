"""
Golden cases — 20 reference quotes (4 per product family).

Expected costs are computed independently from first principles:
    op_cost  = (rate_zl_h / 3600) * (setup_s + cycle_s * qty + extra_s)
    mat_cost = qty_net * scrap_factor * price_per_unit
    svc_cost = qty * price_per_unit
    total    = sum(op_costs) + sum(mat_costs) + sum(svc_costs)
              + packaging_zl + adjustment_zl

P20 machine rates used (zł/h):
    Prościarki do drutu            303
    Giętarka Montorfano            230
    Zgrzewarka Ideal               284
    Zgrzewarka Schlatter           284
    Malarnia proszkowa            1543
    Laser Fiber do blach           460
    Laser Fiber do rur             552
    Giętarka do blach SAFAN        278
    Wykrawarka Prima Power E5      402
    Gratowarka do blach ERNST      283
    Piła taśmowa do rur            230
    Automat do cięcia rur Pedrazzoli 282
    Giętarka rur CNC BLM Elect     298
    Wiertarka kolumnowa            230
    Spawanie ręczne                368
    Robot spawalniczy Fanuc        315
    Montaż                         153
    Pakowanie/montaż               190
    Pakowanie automatyczne         227
"""

import pytest

from metal_calc.data.routing_templates import MESH, SHEET, STRUCTURE, TUBE, WIRE
from metal_calc.engine.calc_form import CalcForm
from metal_calc.engine.calculation import (
    MaterialLine,
    OperationLine,
    OutsideServiceLine,
    Quote,
    QuoteItem,
)
from metal_calc.models.enums import OperationType, PriceProfile

P20 = PriceProfile.MARGIN_20
TOL = 0.01  # zł tolerance for floating-point rounding


def _q(items, number="OF-GC-001"):
    return Quote(
        quote_number=number,
        version=1,
        client="Golden Case Test",
        salesperson="Test",
        rfq_reference="RFQ-GC",
        price_profile=P20,
        calc_date="2025-05-13",
        valid_until="2025-06-13",
        items=items,
    )


def _op_cost(rate_h, setup, cycle, qty, extra=0):
    return (rate_h / 3600) * (setup + cycle * qty + extra)


# ===========================================================================
# WIRE — 4 cases
# ===========================================================================

class TestWireGoldenCases:

    def _wire_form(self, *, qty, mat_kg, scrap, mat_price,
                   bending=False, welding=False, svc=False):
        form = CalcForm.from_template(WIRE, item_name="Drut fi5 S235JR", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=300, cycle_sec=1.5,
        )
        if bending:
            form.fill_operation(
                OperationType.WIRE_BENDING, "Giętarka Montorfano",
                setup_sec=600, cycle_sec=8.0,
            )
        if welding:
            form.fill_operation(
                OperationType.WELDING_SPOT, "Zgrzewarka Ideal",
                setup_sec=300, cycle_sec=5.0,
            )
        form.fill_material(
            "Drut S235JR fi5",
            unit="kg",
            quantity_net=mat_kg,
            scrap_factor=scrap,
            price_per_unit=mat_price,
        )
        if svc:
            form.fill_outside_service(
                service_name="Cynkowanie bebn",
                service_type="cynkowanie_bebn",
                unit="kg",
                quantity=41.0,
                price_per_unit=3.50,
            )
        return form

    def test_wire_1_straightening_only(self):
        """WIRE-1: simple straightening, qty=1000."""
        qty = 1000
        form = CalcForm.from_template(WIRE, item_name="Drut S235JR fi5 kr.", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=300, cycle_sec=1.5,
        )
        form.fill_material("Drut S235JR fi5", unit="kg",
                           quantity_net=80, scrap_factor=1.01, price_per_unit=4.20)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 80 * 1.01 * 4.20                            # 339.36
        op_exp = _op_cost(303, 300, 1.5, qty)                 # 151.5
        total_exp = mat_exp + op_exp                           # 490.86

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - op_exp) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_wire_2_straightening_bending(self):
        """WIRE-2: straightening + bending, qty=500."""
        qty = 500
        form = CalcForm.from_template(WIRE, item_name="Drut S235JR fi6 gięty", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=180, cycle_sec=2.0,
        )
        form.fill_operation(
            OperationType.WIRE_BENDING, "Giętarka Montorfano",
            setup_sec=600, cycle_sec=8.0,
        )
        form.fill_material("Drut S235JR fi6", unit="kg",
                           quantity_net=60, scrap_factor=1.02, price_per_unit=3.90)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 60 * 1.02 * 3.90                            # 238.68
        op1_exp = _op_cost(303, 180, 2.0, qty)                # 99.3167
        op2_exp = _op_cost(230, 600, 8.0, qty)                # 293.8889
        total_exp = mat_exp + op1_exp + op2_exp               # 631.8856

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_wire_3_straightening_spot_welding(self):
        """WIRE-3: straightening + spot welding, qty=200."""
        qty = 200
        form = CalcForm.from_template(WIRE, item_name="Drut fi4 S235JR zgrzewany", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=120, cycle_sec=3.0,
        )
        form.fill_operation(
            OperationType.WELDING_SPOT, "Zgrzewarka Ideal",
            setup_sec=300, cycle_sec=5.0,
        )
        form.fill_material("Drut fi4 S235JR", unit="kg",
                           quantity_net=25, scrap_factor=1.01, price_per_unit=5.00)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 25 * 1.01 * 5.00                            # 126.25
        op1_exp = _op_cost(303, 120, 3.0, qty)                # 60.6
        op2_exp = _op_cost(284, 300, 5.0, qty)                # 102.5556
        total_exp = mat_exp + op1_exp + op2_exp               # 289.4056

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_wire_4_with_outside_service(self):
        """WIRE-4: straightening + galvanizing outside service, qty=300."""
        qty = 300
        form = CalcForm.from_template(WIRE, item_name="Drut S235JR fi3 ocynk.", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=120, cycle_sec=2.0,
        )
        form.fill_material("Drut S235JR fi3", unit="kg",
                           quantity_net=40, scrap_factor=1.02, price_per_unit=4.50)
        form.fill_outside_service(
            service_name="Cynkowanie bebn",
            service_type="cynkowanie_bebn",
            unit="kg",
            quantity=41.0,
            price_per_unit=3.50,
        )

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 40 * 1.02 * 4.50                            # 183.60
        op_exp = _op_cost(303, 120, 2.0, qty)                 # 60.60
        svc_exp = 41.0 * 3.50                                  # 143.50
        total_exp = mat_exp + op_exp + svc_exp                 # 387.70

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - op_exp) < TOL
        assert abs(bd["outside_services_zl"] - svc_exp) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL


# ===========================================================================
# SHEET — 4 cases  (QuoteItem built directly — NESTING has no candidate machines)
# ===========================================================================

class TestSheetGoldenCases:

    def _sheet_item(self, *, qty, mat_kg, scrap, mat_price, ops, svcs=None):
        """Build a SHEET QuoteItem directly with provided OperationLines."""
        return QuoteItem(
            item_name="Blacha test",
            product_family="blacha",
            quantity=qty,
            operations=ops,
            materials=[
                MaterialLine("Blacha DC01", unit="kg",
                             quantity_net=mat_kg, scrap_factor=scrap,
                             price_per_unit=mat_price)
            ],
            outside_services=svcs or [],
        )

    def test_sheet_1_laser_only(self):
        """SHEET-1: laser cutting only, qty=50."""
        qty = 50
        ops = [
            OperationLine("ciecie_laserem", "Laser Fiber do blach",
                          setup_sec=300, cycle_sec=45.0, quantity=qty),
        ]
        item = self._sheet_item(qty=qty, mat_kg=80, scrap=1.05, mat_price=5.50, ops=ops)
        bd = item.cost_breakdown(P20)

        mat_exp = 80 * 1.05 * 5.50                            # 462.0
        op_exp = _op_cost(460, 300, 45.0, qty)                # 325.8333
        total_exp = mat_exp + op_exp                           # 787.8333

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - op_exp) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_sheet_2_laser_and_bending(self):
        """SHEET-2: laser + bending, qty=50."""
        qty = 50
        ops = [
            OperationLine("ciecie_laserem", "Laser Fiber do blach",
                          setup_sec=300, cycle_sec=60.0, quantity=qty),
            OperationLine("giecie_blachy", "Giętarka do blach SAFAN",
                          setup_sec=600, cycle_sec=20.0, quantity=qty),
        ]
        item = self._sheet_item(qty=qty, mat_kg=120, scrap=1.05, mat_price=6.00, ops=ops)
        bd = item.cost_breakdown(P20)

        mat_exp = 120 * 1.05 * 6.00                           # 756.0
        op1_exp = _op_cost(460, 300, 60.0, qty)               # 421.6667
        op2_exp = _op_cost(278, 600, 20.0, qty)               # 123.5556
        total_exp = mat_exp + op1_exp + op2_exp               # 1301.2222

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_sheet_3_laser_and_robot_welding(self):
        """SHEET-3: laser + robot welding, qty=30."""
        qty = 30
        ops = [
            OperationLine("ciecie_laserem", "Laser Fiber do blach",
                          setup_sec=600, cycle_sec=90.0, quantity=qty),
            OperationLine("spawanie_robot", "Robot spawalniczy Fanuc",
                          setup_sec=600, cycle_sec=120.0, quantity=qty),
        ]
        item = self._sheet_item(qty=qty, mat_kg=200, scrap=1.03, mat_price=8.00, ops=ops)
        bd = item.cost_breakdown(P20)

        mat_exp = 200 * 1.03 * 8.00                           # 1648.0
        op1_exp = _op_cost(460, 600, 90.0, qty)               # 421.6667
        op2_exp = _op_cost(315, 600, 120.0, qty)              # 367.5
        total_exp = mat_exp + op1_exp + op2_exp               # 2437.1667

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_sheet_4_laser_and_powder_coating(self):
        """SHEET-4: laser + powder coating, qty=100."""
        qty = 100
        ops = [
            OperationLine("ciecie_laserem", "Laser Fiber do blach",
                          setup_sec=300, cycle_sec=20.0, quantity=qty),
            OperationLine("malowanie_proszkowe", "Malarnia proszkowa",
                          setup_sec=1800, cycle_sec=3.0, quantity=qty),
        ]
        item = self._sheet_item(qty=qty, mat_kg=50, scrap=1.07, mat_price=5.00, ops=ops)
        bd = item.cost_breakdown(P20)

        mat_exp = 50 * 1.07 * 5.00                            # 267.5
        op1_exp = _op_cost(460, 300, 20.0, qty)               # 293.8889
        op2_exp = _op_cost(1543, 1800, 3.0, qty)              # 900.0833
        total_exp = mat_exp + op1_exp + op2_exp               # 1461.4722

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL


# ===========================================================================
# TUBE — 4 cases
# ===========================================================================

class TestTubeGoldenCases:

    def test_tube_1_saw_cutting(self):
        """TUBE-1: bandsaw cutting only, qty=200."""
        qty = 200
        form = CalcForm.from_template(TUBE, item_name="Rura 40x40x2 S235JR", quantity=qty)
        form.fill_operation(
            OperationType.TUBE_CUTTING, "Piła taśmowa do rur",
            setup_sec=180, cycle_sec=3.0,
        )
        form.fill_material("Rura kwadratowa 40x40x2", unit="kg",
                           quantity_net=120, scrap_factor=1.01, price_per_unit=5.80)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 120 * 1.01 * 5.80                           # 702.96
        op_exp = _op_cost(230, 180, 3.0, qty)                 # 49.8333
        total_exp = mat_exp + op_exp                           # 752.7933

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - op_exp) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_tube_2_pedrazzoli_and_bending(self):
        """TUBE-2: Pedrazzoli cutting + BLM bending, qty=100."""
        qty = 100
        form = CalcForm.from_template(TUBE, item_name="Rura okr. fi50 gięta", quantity=qty)
        form.fill_operation(
            OperationType.TUBE_CUTTING, "Automat do cięcia rur Pedrazzoli",
            setup_sec=300, cycle_sec=5.0,
        )
        form.fill_operation(
            OperationType.TUBE_BENDING, "Giętarka rur CNC BLM Elect",
            setup_sec=600, cycle_sec=15.0,
        )
        form.fill_material("Rura okrągła fi50 S235JR", unit="kg",
                           quantity_net=80, scrap_factor=1.02, price_per_unit=6.20)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 80 * 1.02 * 6.20                            # 505.92
        op1_exp = _op_cost(282, 300, 5.0, qty)                # 62.6667
        op2_exp = _op_cost(298, 600, 15.0, qty)               # 173.8333
        total_exp = mat_exp + op1_exp + op2_exp               # 742.42

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_tube_3_saw_drilling_manual_welding(self):
        """TUBE-3: bandsaw + drilling + manual welding, qty=50."""
        qty = 50
        form = CalcForm.from_template(TUBE, item_name="Rura 60x40x3 spawana", quantity=qty)
        form.fill_operation(
            OperationType.TUBE_CUTTING, "Piła taśmowa do rur",
            setup_sec=180, cycle_sec=8.0,
        )
        form.fill_operation(
            OperationType.DRILLING, "Wiertarka kolumnowa",
            setup_sec=300, cycle_sec=10.0,
        )
        form.fill_operation(
            OperationType.WELDING_MANUAL, "Spawanie ręczne",
            setup_sec=600, cycle_sec=30.0,
        )
        form.fill_material("Rura prostokątna 60x40x3", unit="kg",
                           quantity_net=150, scrap_factor=1.01, price_per_unit=7.00)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 150 * 1.01 * 7.00                           # 1060.5
        op1_exp = _op_cost(230, 180, 8.0, qty)                # 37.0556
        op2_exp = _op_cost(230, 300, 10.0, qty)               # 51.1111
        op3_exp = _op_cost(368, 600, 30.0, qty)               # 214.6667
        total_exp = mat_exp + op1_exp + op2_exp + op3_exp     # 1363.3333

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp + op3_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_tube_4_laser_and_robot_welding(self):
        """TUBE-4: tube laser + robot welding, qty=30."""
        qty = 30
        form = CalcForm.from_template(TUBE, item_name="Rura kw. 80x80x4 S355", quantity=qty)
        form.fill_operation(
            OperationType.TUBE_CUTTING, "Laser Fiber do rur",
            setup_sec=600, cycle_sec=20.0,
        )
        form.fill_operation(
            OperationType.WELDING_ROBOT, "Robot spawalniczy Fanuc",
            setup_sec=600, cycle_sec=60.0,
        )
        form.fill_material("Rura kwadratowa 80x80x4 S355", unit="kg",
                           quantity_net=200, scrap_factor=1.02, price_per_unit=8.50)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 200 * 1.02 * 8.50                           # 1734.0
        op1_exp = _op_cost(552, 600, 20.0, qty)               # 184.0
        op2_exp = _op_cost(315, 600, 60.0, qty)               # 210.0
        total_exp = mat_exp + op1_exp + op2_exp               # 2128.0

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL


# ===========================================================================
# MESH — 4 cases
# ===========================================================================

class TestMeshGoldenCases:

    def test_mesh_1_straightening_and_welding(self):
        """MESH-1: straightening + Zgrzewarka Ideal, qty=500."""
        qty = 500
        form = CalcForm.from_template(MESH, item_name="Siatka fi2.5 S235JR", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=300, cycle_sec=1.0,
        )
        form.fill_operation(
            OperationType.WELDING_SPOT, "Zgrzewarka Ideal",
            setup_sec=600, cycle_sec=1.5,
        )
        form.fill_material("Drut S235JR fi2.5", unit="kg",
                           quantity_net=200, scrap_factor=1.03, price_per_unit=3.80)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 200 * 1.03 * 3.80                           # 782.8
        op1_exp = _op_cost(303, 300, 1.0, qty)                # 67.3333
        op2_exp = _op_cost(284, 600, 1.5, qty)                # 106.5
        total_exp = mat_exp + op1_exp + op2_exp               # 956.6333

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_mesh_2_with_packaging(self):
        """MESH-2: straightening + Schlatter + packaging, qty=500."""
        qty = 500
        form = CalcForm.from_template(MESH, item_name="Siatka fi3 S235JR pakowana", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=300, cycle_sec=1.0,
        )
        form.fill_operation(
            OperationType.WELDING_SPOT, "Zgrzewarka Schlatter",
            setup_sec=600, cycle_sec=1.5,
        )
        form.fill_operation(
            OperationType.PACKAGING, "Pakowanie/montaż",
            setup_sec=60, cycle_sec=0.5,
        )
        form.fill_material("Drut S235JR fi3", unit="kg",
                           quantity_net=250, scrap_factor=1.03, price_per_unit=4.00)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 250 * 1.03 * 4.00                           # 1030.0
        op1_exp = _op_cost(303, 300, 1.0, qty)                # 67.3333
        op2_exp = _op_cost(284, 600, 1.5, qty)                # 106.5
        op3_exp = _op_cost(190, 60, 0.5, qty)                 # 16.3611
        total_exp = mat_exp + op1_exp + op2_exp + op3_exp     # 1220.1944

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp + op3_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_mesh_3_with_bending(self):
        """MESH-3: straightening + welding + bending, qty=300."""
        qty = 300
        form = CalcForm.from_template(MESH, item_name="Siatka fi4 S235JR gięta", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=300, cycle_sec=1.5,
        )
        form.fill_operation(
            OperationType.WELDING_SPOT, "Zgrzewarka Ideal",
            setup_sec=600, cycle_sec=2.0,
        )
        form.fill_operation(
            OperationType.WIRE_BENDING, "Giętarka Montorfano",
            setup_sec=300, cycle_sec=3.0,
        )
        form.fill_material("Drut S235JR fi4", unit="kg",
                           quantity_net=150, scrap_factor=1.02, price_per_unit=4.20)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 150 * 1.02 * 4.20                           # 642.6
        op1_exp = _op_cost(303, 300, 1.5, qty)                # 63.125
        op2_exp = _op_cost(284, 600, 2.0, qty)                # 94.6667
        op3_exp = _op_cost(230, 300, 3.0, qty)                # 76.6667
        total_exp = mat_exp + op1_exp + op2_exp + op3_exp     # 877.0583

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp + op3_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_mesh_4_with_powder_coating(self):
        """MESH-4: straightening + welding + powder coating, qty=200."""
        qty = 200
        form = CalcForm.from_template(MESH, item_name="Siatka fi2 malowana", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=300, cycle_sec=2.0,
        )
        form.fill_operation(
            OperationType.WELDING_SPOT, "Zgrzewarka Ideal",
            setup_sec=600, cycle_sec=3.0,
        )
        form.fill_operation(
            OperationType.POWDER_COATING, "Malarnia proszkowa",
            setup_sec=3600, cycle_sec=5.0,
        )
        form.fill_material("Drut S235JR fi2", unit="kg",
                           quantity_net=80, scrap_factor=1.03, price_per_unit=5.50)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 80 * 1.03 * 5.50                            # 453.2
        op1_exp = _op_cost(303, 300, 2.0, qty)                # 58.9167
        op2_exp = _op_cost(284, 600, 3.0, qty)                # 94.6667
        op3_exp = _op_cost(1543, 3600, 5.0, qty)              # 1971.6111
        total_exp = mat_exp + op1_exp + op2_exp + op3_exp     # 2578.3944

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp + op3_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL


# ===========================================================================
# STRUCTURE — 4 cases
# ===========================================================================

class TestStructureGoldenCases:

    def test_structure_1_assembly_only(self):
        """STRUCTURE-1: assembly (mandatory) only, qty=20."""
        qty = 20
        form = CalcForm.from_template(STRUCTURE, item_name="Konstrukcja stalowa A", quantity=qty)
        form.fill_operation(
            OperationType.ASSEMBLY, "Montaż",
            setup_sec=1800, cycle_sec=60.0,
        )
        form.fill_material("Pręt S235JR fi12", unit="kg",
                           quantity_net=50, scrap_factor=1.01, price_per_unit=6.00)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 50 * 1.01 * 6.00                            # 303.0
        op_exp = _op_cost(153, 1800, 60.0, qty)               # 127.5
        total_exp = mat_exp + op_exp                           # 430.5

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - op_exp) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_structure_2_robot_welding_and_assembly(self):
        """STRUCTURE-2: robot welding + assembly, qty=10."""
        qty = 10
        form = CalcForm.from_template(STRUCTURE, item_name="Konstrukcja robotowa B", quantity=qty)
        form.fill_operation(
            OperationType.WELDING_ROBOT, "Robot spawalniczy Fanuc",
            setup_sec=1800, cycle_sec=180.0,
        )
        form.fill_operation(
            OperationType.ASSEMBLY, "Montaż",
            setup_sec=600, cycle_sec=90.0,
        )
        form.fill_material("Blacha S355 4mm", unit="kg",
                           quantity_net=200, scrap_factor=1.04, price_per_unit=7.50)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 200 * 1.04 * 7.50                           # 1560.0
        op1_exp = _op_cost(315, 1800, 180.0, qty)             # 315.0
        op2_exp = _op_cost(153, 600, 90.0, qty)               # 63.75
        total_exp = mat_exp + op1_exp + op2_exp               # 1938.75

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_structure_3_manual_welding_coating_assembly(self):
        """STRUCTURE-3: manual welding + powder coating + assembly, qty=5."""
        qty = 5
        form = CalcForm.from_template(STRUCTURE, item_name="Konstrukcja malowana C", quantity=qty)
        form.fill_operation(
            OperationType.WELDING_MANUAL, "Spawanie ręczne",
            setup_sec=1800, cycle_sec=300.0,
        )
        form.fill_operation(
            OperationType.POWDER_COATING, "Malarnia proszkowa",
            setup_sec=3600, cycle_sec=60.0,
        )
        form.fill_operation(
            OperationType.ASSEMBLY, "Montaż",
            setup_sec=600, cycle_sec=60.0,
        )
        form.fill_material("Blacha S235JR 2mm", unit="kg",
                           quantity_net=100, scrap_factor=1.05, price_per_unit=5.50)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 100 * 1.05 * 5.50                           # 577.5
        op1_exp = _op_cost(368, 1800, 300.0, qty)             # 337.3333
        op2_exp = _op_cost(1543, 3600, 60.0, qty)             # 1671.5833
        op3_exp = _op_cost(153, 600, 60.0, qty)               # 38.25
        total_exp = mat_exp + op1_exp + op2_exp + op3_exp     # 2624.6667

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp + op3_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL

    def test_structure_4_robot_assembly_packaging(self):
        """STRUCTURE-4: robot welding + assembly + packaging, qty=15."""
        qty = 15
        form = CalcForm.from_template(STRUCTURE, item_name="Konstrukcja HEB D", quantity=qty)
        form.fill_operation(
            OperationType.WELDING_ROBOT, "Robot spawalniczy Fanuc",
            setup_sec=1800, cycle_sec=120.0,
        )
        form.fill_operation(
            OperationType.ASSEMBLY, "Montaż",
            setup_sec=600, cycle_sec=60.0,
        )
        form.fill_operation(
            OperationType.PACKAGING, "Pakowanie/montaż",
            setup_sec=300, cycle_sec=10.0,
        )
        form.fill_material("Kształtownik HEB 100", unit="kg",
                           quantity_net=300, scrap_factor=1.01, price_per_unit=9.00)

        item = form.build_quote_item()
        bd = item.cost_breakdown(P20)

        mat_exp = 300 * 1.01 * 9.00                           # 2727.0
        op1_exp = _op_cost(315, 1800, 120.0, qty)             # 315.0
        op2_exp = _op_cost(153, 600, 60.0, qty)               # 63.75
        op3_exp = _op_cost(190, 300, 10.0, qty)               # 23.75
        total_exp = mat_exp + op1_exp + op2_exp + op3_exp     # 3129.5

        assert abs(bd["material_zl"] - mat_exp) < TOL
        assert abs(bd["operations_zl"] - (op1_exp + op2_exp + op3_exp)) < TOL
        assert abs(bd["total_zl"] - total_exp) < TOL


# ===========================================================================
# Quote-level total_cost_zl (two integration smoke tests)
# ===========================================================================

class TestQuoteLevelTotal:

    def test_single_item_quote_total(self):
        """Quote.total_cost_zl() matches sum of item costs (wire case)."""
        qty = 100
        form = CalcForm.from_template(WIRE, item_name="Drut fi5", quantity=qty)
        form.fill_operation(
            OperationType.STRAIGHTENING, "Prościarki do drutu",
            setup_sec=120, cycle_sec=2.5,
        )
        form.fill_material("Drut S235JR fi5", unit="kg",
                           quantity_net=50, scrap_factor=1.02, price_per_unit=4.20)

        item = form.build_quote_item()
        quote = _q([item])
        assert abs(quote.total_cost_zl() - item.total_cost_zl(P20)) < TOL

    def test_multi_item_quote_total(self):
        """Quote.total_cost_zl() sums all items."""
        qty = 100
        form1 = CalcForm.from_template(WIRE, item_name="Drut fi5", quantity=qty)
        form1.fill_operation(OperationType.STRAIGHTENING, "Prościarki do drutu",
                             setup_sec=120, cycle_sec=2.5)
        form1.fill_material("Drut fi5", unit="kg", quantity_net=50,
                            scrap_factor=1.02, price_per_unit=4.20)

        form2 = CalcForm.from_template(WIRE, item_name="Drut fi6", quantity=qty)
        form2.fill_operation(OperationType.STRAIGHTENING, "Prościarki do drutu",
                             setup_sec=120, cycle_sec=3.0)
        form2.fill_material("Drut fi6", unit="kg", quantity_net=60,
                            scrap_factor=1.02, price_per_unit=3.90)

        item1 = form1.build_quote_item()
        item2 = form2.build_quote_item()
        quote = _q([item1, item2])
        expected = item1.total_cost_zl(P20) + item2.total_cost_zl(P20)
        assert abs(quote.total_cost_zl() - expected) < TOL
