"""
Tests for the SQLite repository layer.
All tests use in-memory DB so no file I/O is needed.
"""

import pytest
import datetime

from metal_calc.db.repository import Repository
from metal_calc.engine.calculation import (
    Quote, QuoteItem, OperationLine, MaterialLine,
    OutsideServiceLine, AssumptionEntry
)
from metal_calc.models.enums import PriceProfile, RFQStatus, QuoteStatus


@pytest.fixture
def repo():
    with Repository(":memory:") as r:
        yield r


class TestMachineRatesImport:
    def test_import_returns_52(self, repo):
        n = repo.import_machine_rates("2025-01-01")
        assert n == 52

    def test_idempotent_reimport(self, repo):
        repo.import_machine_rates("2025-01-01")
        n2 = repo.import_machine_rates("2025-01-01")
        assert n2 == 0  # no duplicates

    def test_laser_fiber_stored_correctly(self, repo):
        repo.import_machine_rates("2025-01-01")
        row = repo._conn.execute(
            "SELECT price_0pct_zl_h, price_20pct_zl_h, price_45pct_zl_h "
            "FROM machine_rates WHERE name=?",
            ("Laser Fiber do blach",)
        ).fetchone()
        assert row is not None
        assert row["price_0pct_zl_h"] == 383
        assert row["price_20pct_zl_h"] == 460
        assert row["price_45pct_zl_h"] == 556


class TestRFQ:
    def test_create_rfq(self, repo):
        rfq_id = repo.create_rfq(
            "RFQ-001", "Klient A", "Jan K",
            "2025-05-01T08:00:00", "Zapytanie test"
        )
        assert rfq_id == 1

    def test_get_rfq(self, repo):
        rfq_id = repo.create_rfq("RFQ-002", "Klient B", "Piotr M",
                                  "2025-05-02T09:00:00")
        row = repo.get_rfq(rfq_id)
        assert row["rfq_number"] == "RFQ-002"
        assert row["status"] == "nowe"

    def test_update_rfq_status_missing_data(self, repo):
        rfq_id = repo.create_rfq("RFQ-003", "X", "Y", "2025-05-03T10:00:00")
        repo.update_rfq_status(rfq_id, RFQStatus.MISSING_DATA, ["quantity", "finish"])
        row = repo.get_rfq(rfq_id)
        assert row["status"] == "braki_danych"

    def test_list_rfq_by_status(self, repo):
        repo.create_rfq("RFQ-010", "X", "Y", "2025-05-01T00:00:00")
        repo.create_rfq("RFQ-011", "Z", "W", "2025-05-01T00:00:00")
        repo.update_rfq_status(1, RFQStatus.READY_FOR_CALC)
        ready = repo.list_rfq(RFQStatus.READY_FOR_CALC)
        assert len(ready) == 1

    def test_add_attachment(self, repo):
        rfq_id = repo.create_rfq("RFQ-020", "X", "Y", "2025-05-01T00:00:00")
        att_id = repo.add_rfq_attachment(rfq_id, "rysunek.pdf", "pdf", "/docs/rysunek.pdf")
        assert att_id == 1


class TestQuotePersistence:
    def _make_quote(self) -> Quote:
        q = Quote(
            quote_number="OF-2025-001", version=1,
            client="Klient Test", salesperson="Jan K",
            rfq_reference="RFQ-001",
            price_profile=PriceProfile.MARGIN_0,
            calc_date="2025-05-12", valid_until="2025-06-12",
        )
        item = QuoteItem("Detal laserowy", "blacha", quantity=100)
        item.operations.append(
            OperationLine("Laser cięcie", "Laser Fiber do blach",
                          setup_sec=300, cycle_sec=8, quantity=100)
        )
        item.materials.append(
            MaterialLine("DC01 2mm", "kg", quantity_net=20.0, price_per_unit=4.5)
        )
        item.outside_services.append(
            OutsideServiceLine("Cynkowanie bębn", "cynkowanie_bebn", "kg",
                                quantity=20.0, price_per_unit=2.8)
        )
        item.assumptions.append(
            AssumptionEntry("material_grade", "DC01", "assumed from description", confirmed=False)
        )
        q.items.append(item)
        return q

    def test_save_and_retrieve_quote(self, repo):
        q = self._make_quote()
        qid = repo.save_quote(q)
        row = repo.get_quote(qid)
        assert row["quote_number"] == "OF-2025-001"
        assert row["price_profile"] == 0

    def test_operations_persisted(self, repo):
        q = self._make_quote()
        qid = repo.save_quote(q)
        item_row = repo._conn.execute(
            "SELECT id FROM quote_items WHERE quote_id=?", (qid,)
        ).fetchone()
        ops = repo._conn.execute(
            "SELECT * FROM quote_operations WHERE quote_item_id=?", (item_row["id"],)
        ).fetchall()
        assert len(ops) == 1
        assert ops[0]["machine_name"] == "Laser Fiber do blach"

    def test_materials_persisted(self, repo):
        q = self._make_quote()
        qid = repo.save_quote(q)
        item_id = repo._conn.execute(
            "SELECT id FROM quote_items WHERE quote_id=?", (qid,)
        ).fetchone()["id"]
        mats = repo._conn.execute(
            "SELECT * FROM quote_materials WHERE quote_item_id=?", (item_id,)
        ).fetchall()
        assert len(mats) == 1
        assert mats[0]["material_name"] == "DC01 2mm"

    def test_outside_services_persisted(self, repo):
        q = self._make_quote()
        qid = repo.save_quote(q)
        item_id = repo._conn.execute(
            "SELECT id FROM quote_items WHERE quote_id=?", (qid,)
        ).fetchone()["id"]
        svcs = repo._conn.execute(
            "SELECT * FROM quote_outside_processing WHERE quote_item_id=?", (item_id,)
        ).fetchall()
        assert len(svcs) == 1
        assert svcs[0]["service_name"] == "Cynkowanie bębn"

    def test_assumptions_persisted(self, repo):
        q = self._make_quote()
        qid = repo.save_quote(q)
        assumptions = repo._conn.execute(
            "SELECT * FROM assumptions_log WHERE quote_id=?", (qid,)
        ).fetchall()
        assert len(assumptions) == 1
        assert assumptions[0]["confirmed"] == 0

    def test_update_quote_status(self, repo):
        q = self._make_quote()
        qid = repo.save_quote(q)
        repo.update_quote_status(qid, QuoteStatus.APPROVED)
        row = repo.get_quote(qid)
        assert row["status"] == "zatwierdzona"


class TestMaterialPrices:
    def test_add_and_resolve(self, repo):
        repo.add_material_price(
            "stal_czarna", "S235JR", "drut", "kg",
            price_per_unit=3.20,
            source="cennik_miesięczny",
            valid_from="2025-05-01",
        )
        row = repo.resolve_material_price(
            "stal_czarna", "S235JR", "drut", "2025-05-15"
        )
        assert row is not None
        assert row["price_per_unit"] == 3.20

    def test_priority_procurement_over_monthly(self, repo):
        repo.add_material_price(
            "stal_czarna", "S235JR", "drut", "kg", 3.20,
            "cennik_miesięczny", "2025-05-01"
        )
        repo.add_material_price(
            "stal_czarna", "S235JR", "drut", "kg", 3.50,
            "zapytanie_zaopatrzenie", "2025-05-01"
        )
        row = repo.resolve_material_price("stal_czarna", "S235JR", "drut", "2025-05-15")
        assert row["source"] == "zapytanie_zaopatrzenie"
        assert row["price_per_unit"] == 3.50

    def test_no_price_for_future_date(self, repo):
        repo.add_material_price(
            "stal_czarna", "S235JR", "drut", "kg", 3.20,
            "cennik_miesięczny", "2025-05-01", "2025-05-31"
        )
        row = repo.resolve_material_price("stal_czarna", "S235JR", "drut", "2025-06-15")
        assert row is None
