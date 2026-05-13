"""
SQLite repository — thin persistence layer over the schema.

Responsibilities:
  - initialise DB from schema.sql
  - import machine rates from the frozen data module
  - CRUD for RFQ, Quote, and all sub-tables
  - all writes go through explicit methods so callers never build raw SQL
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from metal_calc.data.machine_rates_2025 import MACHINE_RATES, CENNIK_VERSION
from metal_calc.engine.calculation import (
    Quote, QuoteItem, OperationLine, MaterialLine, OutsideServiceLine, AssumptionEntry
)
from metal_calc.models.enums import RFQStatus, QuoteStatus, PriceProfile

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Repository:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Repository":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with open(_SCHEMA_PATH) as f:
            self._conn.executescript(f.read())
        self._conn.commit()

    # ------------------------------------------------------------------
    # Machine rates import
    # ------------------------------------------------------------------

    def import_machine_rates(
        self,
        valid_from: str,
        valid_to: str | None = None,
    ) -> int:
        """
        Import all 52 machines from the frozen Python module into machine_rates.
        Skips rows already present for the same (name, cennik_version).
        Returns the number of rows inserted.
        """
        inserted = 0
        cur = self._conn.cursor()
        for mr in MACHINE_RATES.values():
            cur.execute(
                "SELECT 1 FROM machine_rates WHERE name=? AND cennik_version=?",
                (mr.name, CENNIK_VERSION),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO machine_rates (
                    lp, name, dept, cennik_version, valid_from, valid_to,
                    wage_piece_zl_h, other_wage_multiplier, total_wages_zl_h,
                    zus_zl_h, ppk_zl_h, direct_labour_zl_h,
                    overhead_dept_pct, overhead_dept_zl_h,
                    overhead_co_pct, overhead_co_zl_h,
                    production_cost_zl_h,
                    selling_cost_pct, selling_cost_zl_h,
                    total_cost_zl_h, rounded_zl_h,
                    price_0pct_zl_h, price_20pct_zl_h, price_45pct_zl_h
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    mr.lp, mr.name, mr.dept, CENNIK_VERSION,
                    valid_from, valid_to,
                    mr.wage_piece_zl_h, mr.other_wage_multiplier, mr.total_wages_zl_h,
                    mr.zus_zl_h, mr.ppk_zl_h, mr.direct_labour_zl_h,
                    mr.overhead_dept_pct, mr.overhead_dept_zl_h,
                    mr.overhead_co_pct, mr.overhead_co_zl_h,
                    mr.production_cost_zl_h,
                    mr.selling_cost_pct, mr.selling_cost_zl_h,
                    mr.total_cost_zl_h, mr.rounded_zl_h,
                    mr.price_0pct_zl_h, mr.price_20pct_zl_h, mr.price_45pct_zl_h,
                ),
            )
            inserted += 1
        self._conn.commit()
        return inserted

    # ------------------------------------------------------------------
    # RFQ
    # ------------------------------------------------------------------

    def create_rfq(
        self,
        rfq_number: str,
        client: str,
        salesperson: str,
        received_at: str,
        subject: str = "",
        body_text: str = "",
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO rfq (rfq_number, client, salesperson, received_at, subject, body_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rfq_number, client, salesperson, received_at, subject, body_text),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def update_rfq_status(
        self,
        rfq_id: int,
        status: RFQStatus,
        missing_fields: list[str] | None = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE rfq SET status=?, missing_fields=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (status.value, json.dumps(missing_fields or []), rfq_id),
        )
        self._conn.commit()

    def add_rfq_attachment(
        self,
        rfq_id: int,
        filename: str,
        file_type: str,
        file_path: str,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO rfq_attachments (rfq_id, filename, file_type, file_path) VALUES (?,?,?,?)",
            (rfq_id, filename, file_type, file_path),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_rfq(self, rfq_id: int) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM rfq WHERE id=?", (rfq_id,)).fetchone()

    def list_rfq(self, status: RFQStatus | None = None) -> list[sqlite3.Row]:
        if status:
            return self._conn.execute(
                "SELECT * FROM rfq WHERE status=? ORDER BY received_at DESC", (status.value,)
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM rfq ORDER BY received_at DESC"
        ).fetchall()

    # ------------------------------------------------------------------
    # Quotes
    # ------------------------------------------------------------------

    def save_quote(self, quote: Quote, rfq_id: int | None = None) -> int:
        """Persist a Quote object and all its items/operations/materials."""
        cur = self._conn.execute(
            """
            INSERT INTO quotes (
                quote_number, version, rfq_id, client, salesperson,
                price_profile, cennik_version, calc_date, valid_until,
                status, tech_notes, commercial_notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                quote.quote_number, quote.version, rfq_id,
                quote.client, quote.salesperson,
                quote.price_profile.value, CENNIK_VERSION,
                quote.calc_date, quote.valid_until,
                QuoteStatus.DRAFT.value,
                quote.tech_notes, quote.commercial_notes,
            ),
        )
        quote_db_id = cur.lastrowid
        assert quote_db_id is not None

        for seq, item in enumerate(quote.items, start=1):
            item_id = self._save_quote_item(quote_db_id, seq, item, quote.price_profile)
            for assumption in item.assumptions:
                self._save_assumption(
                    quote_db_id=quote_db_id,
                    quote_item_id=item_id,
                    assumption=assumption,
                )

        self._conn.commit()
        return quote_db_id

    def _save_quote_item(
        self,
        quote_id: int,
        seq: int,
        item: QuoteItem,
        profile: PriceProfile,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO quote_items (
                quote_id, seq, item_name, product_family,
                quantity, packaging_cost_zl, adjustment_zl
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                quote_id, seq, item.item_name, item.product_family,
                item.quantity, item.packaging_cost_zl, item.adjustment_zl,
            ),
        )
        item_id = cur.lastrowid
        assert item_id is not None

        for op_seq, op in enumerate(item.operations, start=1):
            eff_time = op.effective_time_s()
            rate_s = op.machine_rate.rate_zl_s(profile.value)
            cost = rate_s * eff_time
            self._conn.execute(
                """
                INSERT INTO quote_operations (
                    quote_item_id, seq, operation_name, machine_name,
                    setup_sec, cycle_sec, extra_sec, quantity,
                    rate_zl_s, effective_time_s, cost_zl, note
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id, op_seq, op.operation_name, op.machine_name,
                    op.setup_sec, op.cycle_sec, op.extra_sec, op.quantity,
                    rate_s, eff_time, cost, op.note,
                ),
            )

        for mat in item.materials:
            self._conn.execute(
                """
                INSERT INTO quote_materials (
                    quote_item_id, material_name, unit,
                    quantity_net, scrap_factor, quantity_gross,
                    price_per_unit, price_source, cost_zl
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id, mat.material_name, mat.unit,
                    mat.quantity_net, mat.scrap_factor, mat.quantity_gross,
                    mat.price_per_unit, mat.price_source, mat.cost_zl(),
                ),
            )

        for svc in item.outside_services:
            self._conn.execute(
                """
                INSERT INTO quote_outside_processing (
                    quote_item_id, service_name, service_type, subtype,
                    unit, quantity, price_per_unit, price_source, cost_zl, note
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id, svc.service_name, svc.service_type, "",
                    svc.unit, svc.quantity, svc.price_per_unit,
                    svc.price_source, svc.cost_zl(), svc.note,
                ),
            )

        return item_id

    def _save_assumption(
        self,
        quote_db_id: int,
        quote_item_id: int,
        assumption: AssumptionEntry,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO assumptions_log (
                quote_id, quote_item_id, field_name, assumed_value, reason, confirmed
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                quote_db_id, quote_item_id,
                assumption.field_name, assumption.assumed_value,
                assumption.reason, int(assumption.confirmed),
            ),
        )

    def get_quote(self, quote_id: int) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM quotes WHERE id=?", (quote_id,)
        ).fetchone()

    def list_quotes(
        self, status: QuoteStatus | None = None
    ) -> list[sqlite3.Row]:
        if status:
            return self._conn.execute(
                "SELECT * FROM quotes WHERE status=? ORDER BY calc_date DESC",
                (status.value,),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM quotes ORDER BY calc_date DESC"
        ).fetchall()

    def update_quote_status(self, quote_id: int, status: QuoteStatus) -> None:
        self._conn.execute(
            "UPDATE quotes SET status=?, updated_at=datetime('now') WHERE id=?",
            (status.value, quote_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Material prices
    # ------------------------------------------------------------------

    def add_material_price(
        self,
        material_family: str,
        material_grade: str,
        form: str,
        unit: str,
        price_per_unit: float,
        source: str,
        valid_from: str,
        valid_to: str | None = None,
        source_ref: str = "",
        confirmed: bool = True,
        notes: str = "",
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO material_price_sources (
                material_family, material_grade, form, unit,
                price_per_unit, source, valid_from, valid_to,
                source_ref, confirmed, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                material_family, material_grade, form, unit,
                price_per_unit, source, valid_from, valid_to,
                source_ref, int(confirmed), notes,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def resolve_material_price(
        self,
        material_family: str,
        material_grade: str,
        form: str,
        on_date: str,
    ) -> sqlite3.Row | None:
        """Return the highest-priority valid price on on_date."""
        priority_order = "CASE source " \
            "WHEN 'zapytanie_zaopatrzenie' THEN 1 " \
            "WHEN 'erp_ostatni_ruch' THEN 2 " \
            "WHEN 'cennik_miesięczny' THEN 3 " \
            "WHEN 'regula_tymczasowa' THEN 4 " \
            "ELSE 5 END"
        return self._conn.execute(
            f"""
            SELECT * FROM material_price_sources
            WHERE material_family=? AND material_grade=? AND form=?
              AND valid_from <= ?
              AND (valid_to IS NULL OR valid_to >= ?)
            ORDER BY {priority_order}, created_at DESC
            LIMIT 1
            """,
            (material_family, material_grade, form, on_date, on_date),
        ).fetchone()
