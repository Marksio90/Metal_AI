"""
Tests for engine/sales_card.py
"""

import pytest

from metal_calc.engine.calculation import (
    AssumptionEntry, MaterialLine, OperationLine, OutsideServiceLine,
    Quote, QuoteItem,
)
from metal_calc.engine.sales_card import build_sales_card, format_sales_card_text
from metal_calc.models.enums import PriceProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_item(with_unconfirmed: bool = False, with_service: bool = False) -> QuoteItem:
    ops = [
        OperationLine(
            operation_name="prostowanie_ciecie",
            machine_name="Prościarki do drutu",
            setup_sec=120,
            cycle_sec=2.5,
            quantity=100,
        ),
    ]
    mats = [
        MaterialLine(
            material_name="Drut S235JR fi5",
            unit="kg",
            quantity_net=50.0,
            scrap_factor=1.02,
            price_per_unit=4.20,
            price_source="cennik_miesięczny",
        )
    ]
    svcs = []
    if with_service:
        svcs.append(OutsideServiceLine(
            service_name="Cynkowanie bebn",
            service_type="cynkowanie_bebn",
            unit="kg",
            quantity=51.0,
            price_per_unit=3.80,
        ))
    assumptions = []
    if with_unconfirmed:
        assumptions.append(AssumptionEntry(
            field_name="finish",
            assumed_value="surowe",
            reason="Klient nie podał",
            confirmed=False,
        ))
    return QuoteItem(
        item_name="Drut fi5",
        product_family="drut",
        quantity=100,
        operations=ops,
        materials=mats,
        outside_services=svcs,
        assumptions=assumptions,
    )


def _make_quote(
    with_unconfirmed: bool = False,
    with_service: bool = False,
    profile: PriceProfile = PriceProfile.MARGIN_20,
) -> Quote:
    return Quote(
        quote_number="OF-2025-001",
        version=1,
        client="ACME Sp. z o.o.",
        salesperson="Jan Kowalski",
        rfq_reference="RFQ-42",
        price_profile=profile,
        calc_date="2025-05-13",
        valid_until="2025-06-13",
        tech_notes="Standard wire process",
        commercial_notes="Rabat 5% możliwy przy min. 1000 szt.",
        items=[_make_item(with_unconfirmed=with_unconfirmed, with_service=with_service)],
    )


# ---------------------------------------------------------------------------
# build_sales_card — structure
# ---------------------------------------------------------------------------

class TestBuildSalesCardStructure:
    def test_top_level_keys(self):
        card = build_sales_card(_make_quote())
        for key in (
            "quote_number", "version", "client", "salesperson",
            "rfq_reference", "price_profile", "calc_date", "valid_until",
            "total_cost_zl", "items", "global_risks",
            "tech_notes", "commercial_notes",
        ):
            assert key in card, f"missing key: {key}"

    def test_quote_number_and_version(self):
        card = build_sales_card(_make_quote())
        assert card["quote_number"] == "OF-2025-001"
        assert card["version"] == 1

    def test_price_profile_label(self):
        card = build_sales_card(_make_quote(profile=PriceProfile.MARGIN_45))
        assert card["price_profile"] == "Marża 45%"

    def test_items_count(self):
        card = build_sales_card(_make_quote())
        assert len(card["items"]) == 1

    def test_item_keys(self):
        card = build_sales_card(_make_quote())
        item = card["items"][0]
        for key in (
            "item_name", "product_family", "quantity",
            "material_zl", "operations_zl", "outside_services_zl",
            "packaging_zl", "adjustment_zl", "total_zl", "unit_cost_zl",
            "operations", "materials", "outside_services",
            "assumptions", "risks",
        ):
            assert key in item, f"missing item key: {key}"


# ---------------------------------------------------------------------------
# build_sales_card — values
# ---------------------------------------------------------------------------

class TestBuildSalesCardValues:
    def test_operation_has_seconds(self):
        card = build_sales_card(_make_quote())
        op = card["items"][0]["operations"][0]
        assert op["setup_sec"] == 120
        assert op["cycle_sec"] == 2.5
        assert op["effective_time_s"] == 370.0  # 120 + 2.5*100

    def test_operation_has_rate_zl_h(self):
        card = build_sales_card(_make_quote(profile=PriceProfile.MARGIN_0))
        op = card["items"][0]["operations"][0]
        # Prościarki do drutu price_0pct_zl_h = 253
        assert op["rate_zl_h"] == 253.0

    def test_operation_cost_matches_engine(self):
        q = _make_quote(profile=PriceProfile.MARGIN_20)
        card = build_sales_card(q)
        op_card = card["items"][0]["operations"][0]
        # manual: rate_s = 303/3600; eff=370 → cost = 303/3600*370
        expected = (303 / 3600) * 370
        assert abs(op_card["cost_zl"] - expected) < 0.001

    def test_material_values(self):
        card = build_sales_card(_make_quote())
        mat = card["items"][0]["materials"][0]
        assert mat["quantity_net"] == 50.0
        assert mat["scrap_factor"] == 1.02
        assert abs(mat["quantity_gross"] - 51.0) < 1e-6
        assert abs(mat["cost_zl"] - 51.0 * 4.20) < 1e-4

    def test_outside_service_appears(self):
        card = build_sales_card(_make_quote(with_service=True))
        svcs = card["items"][0]["outside_services"]
        assert len(svcs) == 1
        assert svcs[0]["service_name"] == "Cynkowanie bebn"
        assert abs(svcs[0]["cost_zl"] - 51.0 * 3.80) < 1e-4

    def test_total_cost_matches_sum(self):
        q = _make_quote(with_service=True)
        card = build_sales_card(q)
        item = card["items"][0]
        expected = (
            item["material_zl"]
            + item["operations_zl"]
            + item["outside_services_zl"]
            + item["packaging_zl"]
            + item["adjustment_zl"]
        )
        assert abs(item["total_zl"] - expected) < 1e-4

    def test_unit_cost_equals_total_divided_by_qty(self):
        card = build_sales_card(_make_quote())
        item = card["items"][0]
        assert abs(item["unit_cost_zl"] - item["total_zl"] / 100) < 1e-4


# ---------------------------------------------------------------------------
# build_sales_card — risks and assumptions
# ---------------------------------------------------------------------------

class TestBuildSalesCardRisks:
    def test_no_risk_when_all_confirmed(self):
        card = build_sales_card(_make_quote(with_unconfirmed=False))
        assert card["global_risks"] == []
        assert card["items"][0]["risks"] == []

    def test_unconfirmed_assumption_triggers_item_risk(self):
        card = build_sales_card(_make_quote(with_unconfirmed=True))
        assert len(card["items"][0]["risks"]) == 1

    def test_unconfirmed_assumption_triggers_global_risk(self):
        card = build_sales_card(_make_quote(with_unconfirmed=True))
        assert len(card["global_risks"]) == 1

    def test_assumption_fields(self):
        card = build_sales_card(_make_quote(with_unconfirmed=True))
        a = card["items"][0]["assumptions"][0]
        assert a["field_name"] == "finish"
        assert a["assumed_value"] == "surowe"
        assert a["confirmed"] is False


# ---------------------------------------------------------------------------
# format_sales_card_text
# ---------------------------------------------------------------------------

class TestFormatSalesCardText:
    def test_returns_string(self):
        text = format_sales_card_text(_make_quote())
        assert isinstance(text, str)

    def test_contains_quote_number(self):
        text = format_sales_card_text(_make_quote())
        assert "OF-2025-001" in text

    def test_contains_version(self):
        text = format_sales_card_text(_make_quote())
        assert "wersja 1" in text

    def test_contains_client(self):
        text = format_sales_card_text(_make_quote())
        assert "ACME Sp. z o.o." in text

    def test_contains_effective_time(self):
        text = format_sales_card_text(_make_quote())
        assert "370" in text

    def test_contains_risk_warning_when_unconfirmed(self):
        text = format_sales_card_text(_make_quote(with_unconfirmed=True))
        assert "RYZYKA" in text or "!!!" in text

    def test_no_risk_warning_when_clean(self):
        text = format_sales_card_text(_make_quote(with_unconfirmed=False))
        assert "!!!" not in text

    def test_contains_tech_notes(self):
        text = format_sales_card_text(_make_quote())
        assert "Standard wire process" in text

    def test_contains_commercial_notes(self):
        text = format_sales_card_text(_make_quote())
        assert "Rabat 5%" in text

    def test_total_appears_in_footer(self):
        q = _make_quote()
        expected = round(q.total_cost_zl(), 2)
        text = format_sales_card_text(q)
        assert f"{expected:.2f}" in text
