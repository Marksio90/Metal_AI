"""
Unit tests for the calculation engine.

Tests cover:
  - czas_efektywny_s formula
  - koszt_operacji formula
  - koszt_pozycji aggregation
  - cost breakdown correctness
  - edge cases (zero times, single piece, large batch)
  - 10 golden reference wycenas across all 5 product families
"""

import math
import pytest

from metal_calc.engine.calculation import (
    OperationLine, MaterialLine, OutsideServiceLine,
    AssumptionEntry, QuoteItem, Quote
)
from metal_calc.models.enums import PriceProfile


P0  = PriceProfile.MARGIN_0
P20 = PriceProfile.MARGIN_20
P45 = PriceProfile.MARGIN_45


# ---------------------------------------------------------------------------
# OperationLine unit tests
# ---------------------------------------------------------------------------

class TestOperationLine:
    def test_effective_time_no_extra(self):
        op = OperationLine("Test", "Laser Fiber do blach", setup_sec=60, cycle_sec=10, quantity=100)
        # 60 + 10*100 + 0 = 1060
        assert op.effective_time_s() == 1060.0

    def test_effective_time_with_extra(self):
        op = OperationLine("Test", "Laser Fiber do blach", setup_sec=60, cycle_sec=10, quantity=100, extra_sec=30)
        assert op.effective_time_s() == 1090.0

    def test_effective_time_setup_only(self):
        op = OperationLine("Test", "Montaż", setup_sec=300, cycle_sec=0, quantity=1)
        assert op.effective_time_s() == 300.0

    def test_cost_zl_p0_laser(self):
        # 3600 s on Laser Fiber do blach at 0% must equal 383 zł
        op = OperationLine("Laser", "Laser Fiber do blach", setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 383.0, rel_tol=1e-9)

    def test_cost_zl_p0_spawanie(self):
        # 3600 s Spawanie ręczne at 0% = 307 zł
        op = OperationLine("Spawn", "Spawanie ręczne", setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 307.0, rel_tol=1e-9)

    def test_cost_zl_p0_malarnia(self):
        # 3600 s Malarnia proszkowa at 0% = 1285 zł
        op = OperationLine("Mal", "Malarnia proszkowa", setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 1285.0, rel_tol=1e-9)

    def test_cost_zl_p20_montaz(self):
        # 3600 s Montaż at 20% = 153 zł
        op = OperationLine("Mnt", "Montaż", setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P20), 153.0, rel_tol=1e-9)

    def test_cost_zl_p45_cynkownia(self):
        # 3600 s Cynkownia at 45% = 282 zł
        op = OperationLine("Cyn", "Cynkownia", setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P45), 282.0, rel_tol=1e-9)

    def test_cost_per_piece(self):
        # 100 pieces, 10 s each at Montaż 0%
        # rate = 128/3600, time = 10*100 = 1000 s
        # cost = (128/3600)*1000 = 35.555... zł
        # per piece = cost/100
        op = OperationLine("Mnt", "Montaż", setup_sec=0, cycle_sec=10, quantity=100)
        expected_total = (128 / 3600) * 1000
        assert math.isclose(op.cost_zl(P0), expected_total, rel_tol=1e-9)
        assert math.isclose(op.cost_zl_per_piece(P0), expected_total / 100, rel_tol=1e-9)

    def test_zero_quantity_per_piece(self):
        op = OperationLine("Test", "Montaż", setup_sec=0, cycle_sec=10, quantity=0)
        assert op.cost_zl_per_piece(P0) == 0.0


# ---------------------------------------------------------------------------
# MaterialLine unit tests
# ---------------------------------------------------------------------------

class TestMaterialLine:
    def test_cost_no_scrap(self):
        mat = MaterialLine("S235JR Ø5mm", "kg", quantity_net=10.0, price_per_unit=3.5)
        assert math.isclose(mat.cost_zl(), 35.0, rel_tol=1e-9)

    def test_cost_with_scrap(self):
        mat = MaterialLine("DC01", "kg", quantity_net=10.0, scrap_factor=1.05, price_per_unit=4.0)
        assert math.isclose(mat.cost_zl(), 10.0 * 1.05 * 4.0, rel_tol=1e-9)

    def test_quantity_gross(self):
        mat = MaterialLine("DC01", "kg", quantity_net=20.0, scrap_factor=1.1, price_per_unit=1.0)
        assert math.isclose(mat.quantity_gross, 22.0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# OutsideServiceLine unit tests
# ---------------------------------------------------------------------------

class TestOutsideServiceLine:
    def test_cost(self):
        svc = OutsideServiceLine("Cynkowanie bębn", "cynkowanie_bebn", "kg",
                                  quantity=50.0, price_per_unit=2.8)
        assert math.isclose(svc.cost_zl(), 140.0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# QuoteItem aggregation
# ---------------------------------------------------------------------------

class TestQuoteItem:
    def _make_item(self) -> QuoteItem:
        item = QuoteItem("Koszyk drut", "drut", quantity=200)
        item.operations.append(
            OperationLine("Prostowanie", "Prościarki do drutu",
                          setup_sec=120, cycle_sec=5, quantity=200)
        )
        item.materials.append(
            MaterialLine("S235JR Ø4mm", "kg",
                          quantity_net=40.0, price_per_unit=3.2)
        )
        return item

    def test_material_cost(self):
        item = self._make_item()
        assert math.isclose(item.total_material_cost_zl(), 128.0, rel_tol=1e-9)

    def test_operation_cost_p0(self):
        item = self._make_item()
        # setup=120, cycle=5*200=1000, total=1120 s, rate=253/3600
        expected = (253 / 3600) * 1120
        assert math.isclose(item.total_operation_cost_zl(P0), expected, rel_tol=1e-9)

    def test_total_cost_p0(self):
        item = self._make_item()
        expected = 128.0 + (253 / 3600) * 1120
        assert math.isclose(item.total_cost_zl(P0), expected, rel_tol=1e-9)

    def test_breakdown_keys(self):
        item = self._make_item()
        bd = item.cost_breakdown(P0)
        for key in ["material_zl", "operations_zl", "outside_services_zl",
                    "packaging_zl", "adjustment_zl", "total_zl", "unit_cost_zl"]:
            assert key in bd

    def test_no_unconfirmed_assumptions_default(self):
        item = self._make_item()
        assert not item.has_unconfirmed_assumptions()

    def test_unconfirmed_assumption_flagged(self):
        item = self._make_item()
        item.assumptions.append(
            AssumptionEntry("material_grade", "S235JR", "assumed from description", confirmed=False)
        )
        assert item.has_unconfirmed_assumptions()

    def test_outside_service_cost_aggregated(self):
        item = self._make_item()
        item.outside_services.append(
            OutsideServiceLine("Cynkowanie", "cynkowanie_bebn", "kg",
                                quantity=40.0, price_per_unit=2.5)
        )
        assert math.isclose(item.total_outside_service_cost_zl(), 100.0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Golden reference wycenas — 10 cases, all 5 families
# ---------------------------------------------------------------------------

class TestGoldenCases:
    """
    Calculated by hand from Excel stawki, then verified here.
    Format: setup_sec, cycle_sec, quantity, machine → expected cost at 0%
    """

    def test_wire_simple_segment(self):
        """Prosty odcinek drutu: Prościarki, 3600 s → 253 zł."""
        op = OperationLine("Prostowanie", "Prościarki do drutu",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 253.0, rel_tol=1e-9)

    def test_wire_bent_detail(self):
        """Detal z drutu z gięciem: Prościarki 600s + Giętarka Montorfano 1200s."""
        op1 = OperationLine("Prost.", "Prościarki do drutu",
                            setup_sec=60, cycle_sec=3, quantity=200)
        op2 = OperationLine("Gięcie", "Giętarka Montorfano",
                            setup_sec=120, cycle_sec=4, quantity=200)
        cost1 = op1.cost_zl(P0)  # (60+600) * 253/3600
        cost2 = op2.cost_zl(P0)  # (120+800) * 192/3600
        assert math.isclose(cost1, (60 + 3 * 200) * (253 / 3600), rel_tol=1e-9)
        assert math.isclose(cost2, (120 + 4 * 200) * (192 / 3600), rel_tol=1e-9)

    def test_sheet_laser_cut(self):
        """Detal blaszany cięty laserem: 3600 s → 383 zł at 0%."""
        op = OperationLine("Laser", "Laser Fiber do blach",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 383.0, rel_tol=1e-9)

    def test_sheet_laser_and_bending(self):
        """Detal cięty i gięty: Laser 1800s + SAFAN 900s."""
        op1 = OperationLine("Laser", "Laser Fiber do blach",
                            setup_sec=300, cycle_sec=7.5, quantity=200)
        op2 = OperationLine("Gięcie", "Giętarka do blach SAFAN",
                            setup_sec=180, cycle_sec=4.5, quantity=200)
        assert math.isclose(op1.cost_zl(P0), (300 + 7.5 * 200) * (383 / 3600), rel_tol=1e-9)
        assert math.isclose(op2.cost_zl(P0), (180 + 4.5 * 200) * (232 / 3600), rel_tol=1e-9)

    def test_tube_cut(self):
        """Rura cięta: Laser Fiber do rur 3600 s → 460 zł at 0%."""
        op = OperationLine("Laser rur", "Laser Fiber do rur",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 460.0, rel_tol=1e-9)

    def test_tube_cut_and_bent(self):
        """Rura gięta: cięcie Pedrazzoli + gięcie BLM."""
        op1 = OperationLine("Cięcie", "Automat do cięcia rur Pedrazzoli",
                            setup_sec=120, cycle_sec=6, quantity=100)
        op2 = OperationLine("Gięcie", "Giętarka rur CNC BLM Elect",
                            setup_sec=180, cycle_sec=12, quantity=100)
        assert math.isclose(op1.cost_zl(P0), (120 + 600) * (235 / 3600), rel_tol=1e-9)
        assert math.isclose(op2.cost_zl(P0), (180 + 1200) * (248 / 3600), rel_tol=1e-9)

    def test_welded_assembly(self):
        """Prosty zespół spawany: Robot Fanuc 3600 s → 262 zł at 0%."""
        op = OperationLine("Spawanie", "Robot spawalniczy Fanuc",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 262.0, rel_tol=1e-9)

    def test_galvanized_detail(self):
        """Detal cynkowany: 3600 s Cynkownia at 0% = 195 zł."""
        op = OperationLine("Cynkowanie", "Cynkownia",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 195.0, rel_tol=1e-9)

    def test_powder_coated_detail(self):
        """Detal malowany: 3600 s Malarnia proszkowa at 0% = 1285 zł."""
        op = OperationLine("Malowanie", "Malarnia proszkowa",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P0), 1285.0, rel_tol=1e-9)

    def test_final_assembly(self):
        """Montaż końcowy: 3600 s Montaż at 20% = 153 zł."""
        op = OperationLine("Montaż", "Montaż",
                           setup_sec=3600, cycle_sec=0, quantity=1)
        assert math.isclose(op.cost_zl(P20), 153.0, rel_tol=1e-9)

    def test_full_quote_item_wire_basket(self):
        """
        Full item: drut koszyk, 500 szt.
        - Prostowanie: setup=300s, cycle=2s/szt → 1300s
        - Zgrzewanie Ideal: setup=180s, cycle=8s/szt → 4180s
        - Malowanie proszkowe: setup=120s, cycle=15s/szt → 7620s
        - Materiał: 25 kg S235JR @ 3.20 zł/kg
        Verified at 0% margin.
        """
        qty = 500
        item = QuoteItem("Koszyk drut Ø4", "drut", quantity=qty)
        item.operations.extend([
            OperationLine("Prostowanie", "Prościarki do drutu",
                          setup_sec=300, cycle_sec=2, quantity=qty),
            OperationLine("Zgrzewanie", "Zgrzewarka Ideal",
                          setup_sec=180, cycle_sec=8, quantity=qty),
            OperationLine("Malowanie", "Malarnia proszkowa",
                          setup_sec=120, cycle_sec=15, quantity=qty),
        ])
        item.materials.append(
            MaterialLine("S235JR Ø4mm", "kg",
                          quantity_net=25.0, scrap_factor=1.03, price_per_unit=3.20)
        )

        expected_op_cost = (
            (300 + 2 * 500)  * (253 / 3600) +
            (180 + 8 * 500)  * (237 / 3600) +
            (120 + 15 * 500) * (1285 / 3600)
        )
        expected_mat_cost = 25.0 * 1.03 * 3.20
        expected_total = expected_op_cost + expected_mat_cost

        assert math.isclose(item.total_operation_cost_zl(P0), expected_op_cost, rel_tol=1e-9)
        assert math.isclose(item.total_material_cost_zl(), expected_mat_cost, rel_tol=1e-9)
        assert math.isclose(item.total_cost_zl(P0), expected_total, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Quote summary
# ---------------------------------------------------------------------------

class TestQuoteSummary:
    def test_summary_structure(self):
        quote = Quote(
            quote_number="OF-2025-001", version=1,
            client="Klient Testowy", salesperson="Jan Kowalski",
            rfq_reference="RFQ-001",
            price_profile=P20,
            calc_date="2025-05-12", valid_until="2025-06-12",
        )
        item = QuoteItem("Test", "blacha", quantity=10)
        item.operations.append(
            OperationLine("Laser", "Laser Fiber do blach",
                          setup_sec=600, cycle_sec=30, quantity=10)
        )
        quote.items.append(item)

        s = quote.summary()
        assert s["quote_number"] == "OF-2025-001"
        assert s["price_profile"] == "Marża 20%"
        assert "total_cost_zl" in s
        assert len(s["items"]) == 1

    def test_unconfirmed_assumption_surfaced_in_summary(self):
        quote = Quote(
            quote_number="OF-2025-002", version=1,
            client="X", salesperson="Y", rfq_reference="R",
            price_profile=P0,
            calc_date="2025-05-12", valid_until="2025-06-12",
        )
        item = QuoteItem("Part", "drut", quantity=5)
        item.assumptions.append(
            AssumptionEntry("material_grade", "S235JR", "assumed", confirmed=False)
        )
        quote.items.append(item)
        s = quote.summary()
        assert s["risk_flags"]["unconfirmed_assumptions"] is True
