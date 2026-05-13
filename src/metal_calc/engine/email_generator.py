"""
EmailGenerator — builds Polish-language email packages for the salesperson.

Two public entry points:

  build_offer_email(quote, ...)
      → dict with 'subject', 'body', 'risk_note'
        Complete offer for a fully calculated quote.

  build_full_salesperson_package(quote, ...)
      → dict with 'email_subject', 'email_body', 'sales_card_text', 'risk_note'
        One-call bundle: email draft + calculation card text.

For the missing-data reply (RFQ incomplete), use:
  metal_calc.engine.rfq_intake.build_missing_data_reply()
"""

from __future__ import annotations

from metal_calc.engine.calculation import Quote
from metal_calc.engine.sales_card import build_sales_card, format_sales_card_text


def build_offer_email(
    quote: Quote,
    *,
    sender_name: str = "Dział Sprzedaży",
    sender_company: str = "Metal AI Sp. z o.o.",
    include_price: bool = True,
    include_validity: bool = True,
) -> dict[str, str]:
    """
    Generate a professional Polish-language offer email.

    Returns dict with keys:
      subject   — ready email subject line
      body      — email body (plain text, client-facing)
      risk_note — internal note (NOT for client); empty string if no risks
    """
    card = build_sales_card(quote)
    total = card["total_cost_zl"]
    profile_label = card["price_profile"]

    subject = (
        f"Oferta handlowa nr {quote.quote_number} (wer. {quote.version})"
        f" — {quote.client}"
    )

    # Price breakdown block
    price_block = ""
    if include_price:
        item_lines = []
        for item in card["items"]:
            item_lines.append(
                f"  • {item['item_name']}: "
                f"{item['quantity']} szt. "
                f"@ {item['unit_cost_zl']:.2f} zł/szt."
                f" = {item['total_zl']:.2f} zł"
            )
        price_block = (
            "\n\nZakres wyceny:\n"
            + "\n".join(item_lines)
            + f"\n\nŁączna wartość netto: {total:.2f} zł ({profile_label})"
        )

    # Validity block
    validity_block = (
        f"\n\nOferta ważna do: {quote.valid_until}." if include_validity else ""
    )

    # Unconfirmed assumptions — ask client to confirm
    all_assumptions = [a for item in card["items"] for a in item["assumptions"]]
    unconfirmed = [a for a in all_assumptions if not a["confirmed"]]
    assumption_block = ""
    if unconfirmed:
        a_lines = [
            "\n\nW wycenie przyjęto następujące założenia wymagające potwierdzenia:"
        ]
        for a in unconfirmed:
            a_lines.append(
                f"  • {a['field_name']}: {a['assumed_value']} — {a['reason']}"
            )
        assumption_block = "\n".join(a_lines)

    # Commercial notes
    commercial_block = (
        f"\n\n{quote.commercial_notes}" if quote.commercial_notes else ""
    )

    body = (
        "Szanowni Państwo,\n"
        "\n"
        f"Dziękujemy za przesłanie zapytania ofertowego"
        f" (RFQ ref.: {quote.rfq_reference}).\n"
        f"W odpowiedzi na Państwa zapytanie, z przyjemnością przedstawiamy ofertę"
        f" nr {quote.quote_number} (wersja {quote.version})."
        + price_block
        + assumption_block
        + validity_block
        + "\n\n"
        "Warunki ogólne:\n"
        "  • Ceny netto — do cen należy doliczyć podatek VAT w obowiązującej stawce.\n"
        "  • Termin realizacji do ustalenia po potwierdzeniu zamówienia.\n"
        "  • Niniejsza oferta nie stanowi zamówienia ani wiążącej umowy."
        + commercial_block
        + "\n\n"
        "Pozostajemy do Państwa dyspozycji w razie dodatkowych pytań.\n"
        "\n"
        f"Z wyrazami szacunku,\n"
        f"{sender_name}\n"
        f"{sender_company}"
    )

    # Internal risk note — never send to client
    risk_note = ""
    if card["global_risks"]:
        risk_note = (
            "[UWAGA WEWNĘTRZNA — nie wysyłać klientowi]\n"
            + "\n".join(f"  • {r}" for r in card["global_risks"])
        )

    return {
        "subject": subject,
        "body": body,
        "risk_note": risk_note,
    }


def build_full_salesperson_package(
    quote: Quote,
    *,
    sender_name: str = "Dział Sprzedaży",
    sender_company: str = "Metal AI Sp. z o.o.",
) -> dict[str, str]:
    """
    One-call salesperson bundle:
      email_subject    — subject line ready to paste
      email_body       — client-facing email body
      sales_card_text  — full calculation card text (internal)
      risk_note        — internal risk warnings (empty if none)
    """
    email = build_offer_email(
        quote,
        sender_name=sender_name,
        sender_company=sender_company,
    )
    card_text = format_sales_card_text(quote)

    return {
        "email_subject": email["subject"],
        "email_body": email["body"],
        "sales_card_text": card_text,
        "risk_note": email["risk_note"],
    }
