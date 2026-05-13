"""
Tests for engine/email_generator.py
"""

import pytest

from metal_calc.engine.calculation import (
    AssumptionEntry, MaterialLine, OperationLine, Quote, QuoteItem,
)
from metal_calc.engine.email_generator import (
    build_full_salesperson_package,
    build_offer_email,
)
from metal_calc.models.enums import PriceProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_quote(with_unconfirmed: bool = False) -> Quote:
    ops = [
        OperationLine(
            operation_name="prostowanie_ciecie",
            machine_name="Prościarki do drutu",
            setup_sec=120,
            cycle_sec=2.5,
            quantity=200,
        ),
    ]
    mats = [
        MaterialLine(
            material_name="Drut S235JR fi6",
            unit="kg",
            quantity_net=100.0,
            scrap_factor=1.02,
            price_per_unit=4.10,
        )
    ]
    assumptions = []
    if with_unconfirmed:
        assumptions.append(AssumptionEntry(
            field_name="finish",
            assumed_value="surowe",
            reason="Brak informacji od klienta",
            confirmed=False,
        ))
    item = QuoteItem(
        item_name="Drut fi6 S235JR x200",
        product_family="drut",
        quantity=200,
        operations=ops,
        materials=mats,
        assumptions=assumptions,
    )
    return Quote(
        quote_number="OF-2025-099",
        version=2,
        client="Beta Metal S.A.",
        salesperson="Anna Nowak",
        rfq_reference="RFQ-77",
        price_profile=PriceProfile.MARGIN_20,
        calc_date="2025-05-13",
        valid_until="2025-06-13",
        commercial_notes="Warunki płatności: 30 dni.",
        items=[item],
    )


# ---------------------------------------------------------------------------
# build_offer_email — structure
# ---------------------------------------------------------------------------

class TestBuildOfferEmailStructure:
    def test_returns_dict_with_required_keys(self):
        result = build_offer_email(_make_quote())
        assert "subject" in result
        assert "body" in result
        assert "risk_note" in result

    def test_subject_contains_quote_number(self):
        result = build_offer_email(_make_quote())
        assert "OF-2025-099" in result["subject"]

    def test_subject_contains_version(self):
        result = build_offer_email(_make_quote())
        assert "wer. 2" in result["subject"]

    def test_subject_contains_client(self):
        result = build_offer_email(_make_quote())
        assert "Beta Metal S.A." in result["subject"]


# ---------------------------------------------------------------------------
# build_offer_email — body content
# ---------------------------------------------------------------------------

class TestBuildOfferEmailBody:
    def test_body_is_string(self):
        result = build_offer_email(_make_quote())
        assert isinstance(result["body"], str)

    def test_body_contains_rfq_reference(self):
        result = build_offer_email(_make_quote())
        assert "RFQ-77" in result["body"]

    def test_body_contains_total_price(self):
        q = _make_quote()
        result = build_offer_email(q)
        total = round(q.total_cost_zl(), 2)
        assert f"{total:.2f}" in result["body"]

    def test_body_contains_item_name(self):
        result = build_offer_email(_make_quote())
        assert "Drut fi6 S235JR x200" in result["body"]

    def test_body_contains_validity(self):
        result = build_offer_email(_make_quote())
        assert "2025-06-13" in result["body"]

    def test_body_contains_commercial_notes(self):
        result = build_offer_email(_make_quote())
        assert "Warunki płatności" in result["body"]

    def test_body_contains_sender_name(self):
        result = build_offer_email(_make_quote(), sender_name="Mariusz Testowy")
        assert "Mariusz Testowy" in result["body"]

    def test_body_contains_sender_company(self):
        result = build_offer_email(_make_quote(), sender_company="TestCorp Sp. z o.o.")
        assert "TestCorp Sp. z o.o." in result["body"]

    def test_no_price_in_body_when_disabled(self):
        q = _make_quote()
        result = build_offer_email(q, include_price=False)
        total_str = f"{round(q.total_cost_zl(), 2):.2f}"
        assert total_str not in result["body"]

    def test_no_validity_in_body_when_disabled(self):
        result = build_offer_email(_make_quote(), include_validity=False)
        assert "2025-06-13" not in result["body"]


# ---------------------------------------------------------------------------
# build_offer_email — assumptions and risks
# ---------------------------------------------------------------------------

class TestBuildOfferEmailRisks:
    def test_unconfirmed_assumption_in_body(self):
        result = build_offer_email(_make_quote(with_unconfirmed=True))
        assert "finish" in result["body"]
        assert "surowe" in result["body"]

    def test_risk_note_populated_when_unconfirmed(self):
        result = build_offer_email(_make_quote(with_unconfirmed=True))
        assert result["risk_note"] != ""
        assert "UWAGA WEWNĘTRZNA" in result["risk_note"]

    def test_risk_note_empty_when_no_risks(self):
        result = build_offer_email(_make_quote(with_unconfirmed=False))
        assert result["risk_note"] == ""

    def test_risk_note_not_in_body(self):
        result = build_offer_email(_make_quote(with_unconfirmed=True))
        assert "UWAGA WEWNĘTRZNA" not in result["body"]


# ---------------------------------------------------------------------------
# build_full_salesperson_package
# ---------------------------------------------------------------------------

class TestBuildFullSalespersonPackage:
    def test_returns_all_keys(self):
        pkg = build_full_salesperson_package(_make_quote())
        for key in ("email_subject", "email_body", "sales_card_text", "risk_note"):
            assert key in pkg, f"missing key: {key}"

    def test_email_subject_matches_offer_email(self):
        q = _make_quote()
        pkg = build_full_salesperson_package(q)
        email = build_offer_email(q)
        assert pkg["email_subject"] == email["subject"]

    def test_sales_card_text_contains_quote_number(self):
        pkg = build_full_salesperson_package(_make_quote())
        assert "OF-2025-099" in pkg["sales_card_text"]

    def test_sales_card_text_contains_karta_kalkulacji(self):
        pkg = build_full_salesperson_package(_make_quote())
        assert "KARTA KALKULACJI" in pkg["sales_card_text"]

    def test_risk_note_propagated_correctly(self):
        pkg_clean = build_full_salesperson_package(_make_quote(with_unconfirmed=False))
        pkg_risky = build_full_salesperson_package(_make_quote(with_unconfirmed=True))
        assert pkg_clean["risk_note"] == ""
        assert "UWAGA WEWNĘTRZNA" in pkg_risky["risk_note"]

    def test_custom_sender_info(self):
        pkg = build_full_salesperson_package(
            _make_quote(),
            sender_name="Tomasz Sprzedaży",
            sender_company="Acme Metal Polska",
        )
        assert "Tomasz Sprzedaży" in pkg["email_body"]
        assert "Acme Metal Polska" in pkg["email_body"]
