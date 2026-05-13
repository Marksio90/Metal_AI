"""
SalesCard — human-readable calculation card for the salesperson.

build_sales_card()       → structured dict (machine-readable)
format_sales_card_text() → formatted Polish-language text block

Card contains:
  - quote header: number, version, price profile, dates
  - per-item cost breakdown with operations (seconds shown), materials, outside services
  - assumptions list (confirmed / unconfirmed)
  - risk flags per item and globally
"""

from __future__ import annotations

from metal_calc.engine.calculation import Quote


def build_sales_card(quote: Quote) -> dict:
    """Return a fully structured dict representing the complete sales card."""
    profile = quote.price_profile
    items_out = []

    for item in quote.items:
        bd = item.cost_breakdown(profile)

        ops_detail = []
        for op in item.operations:
            eff = op.effective_time_s()
            rate_s = op.machine_rate.rate_zl_s(profile.value)
            ops_detail.append({
                "operation_name": op.operation_name,
                "machine_name": op.machine_name,
                "setup_sec": op.setup_sec,
                "cycle_sec": op.cycle_sec,
                "extra_sec": op.extra_sec,
                "quantity": op.quantity,
                "effective_time_s": round(eff, 3),
                "effective_time_min": round(eff / 60, 4),
                "rate_zl_h": round(rate_s * 3600, 2),
                "rate_zl_s": round(rate_s, 8),
                "cost_zl": round(op.cost_zl(profile), 4),
                "cost_zl_per_piece": round(op.cost_zl_per_piece(profile), 4),
                "note": op.note,
            })

        mats_detail = [
            {
                "material_name": m.material_name,
                "unit": m.unit,
                "quantity_net": m.quantity_net,
                "scrap_factor": m.scrap_factor,
                "quantity_gross": round(m.quantity_gross, 4),
                "price_per_unit": m.price_per_unit,
                "price_source": m.price_source,
                "cost_zl": round(m.cost_zl(), 4),
                "note": m.note,
            }
            for m in item.materials
        ]

        svcs_detail = [
            {
                "service_name": s.service_name,
                "service_type": s.service_type,
                "unit": s.unit,
                "quantity": s.quantity,
                "price_per_unit": s.price_per_unit,
                "price_source": s.price_source,
                "cost_zl": round(s.cost_zl(), 4),
                "note": s.note,
            }
            for s in item.outside_services
        ]

        assumptions_detail = [
            {
                "field_name": a.field_name,
                "assumed_value": a.assumed_value,
                "reason": a.reason,
                "confirmed": a.confirmed,
            }
            for a in item.assumptions
        ]

        item_risks: list[str] = []
        if item.has_unconfirmed_assumptions():
            item_risks.append(
                "Niezatwierdzone założenia — wycena wymaga weryfikacji przed wysłaniem"
            )

        items_out.append({
            **bd,
            "item_name": item.item_name,
            "product_family": item.product_family,
            "operations": ops_detail,
            "materials": mats_detail,
            "outside_services": svcs_detail,
            "assumptions": assumptions_detail,
            "risks": item_risks,
        })

    global_risks: list[str] = []
    if quote.has_any_unconfirmed_assumptions():
        global_risks.append(
            "Wycena zawiera niezatwierdzone założenia — wymagana weryfikacja przed wysłaniem"
        )

    return {
        "quote_number": quote.quote_number,
        "version": quote.version,
        "client": quote.client,
        "salesperson": quote.salesperson,
        "rfq_reference": quote.rfq_reference,
        "price_profile": profile.label(),
        "calc_date": quote.calc_date,
        "valid_until": quote.valid_until,
        "total_cost_zl": round(quote.total_cost_zl(), 4),
        "items": items_out,
        "global_risks": global_risks,
        "tech_notes": quote.tech_notes,
        "commercial_notes": quote.commercial_notes,
    }


# ---------------------------------------------------------------------------
# Text formatter
# ---------------------------------------------------------------------------

def format_sales_card_text(quote: Quote) -> str:
    """Format the sales card as a Polish-language text block."""
    card = build_sales_card(quote)
    L: list[str] = []

    sep = "=" * 62

    L += [
        sep,
        "KARTA KALKULACJI",
        f"Oferta nr:    {card['quote_number']}  (wersja {card['version']})",
        f"Klient:       {card['client']}",
        f"Handlowiec:   {card['salesperson']}",
        f"RFQ ref.:     {card['rfq_reference']}",
        f"Profil ceny:  {card['price_profile']}",
        f"Data:         {card['calc_date']}   Ważna do: {card['valid_until']}",
        sep,
    ]

    for idx, item in enumerate(card["items"], start=1):
        L += [
            "",
            f"--- Pozycja {idx}: {item['item_name']} ---",
            f"  Rodzina:   {item['product_family']}",
            f"  Ilość:     {item['quantity']} szt.",
        ]

        # Operations
        L.append("  Operacje:")
        for op in item["operations"]:
            L.append(
                f"    • {op['operation_name']:<32} [{op['machine_name']}]"
                f"  setup={op['setup_sec']}s  takt={op['cycle_sec']}s"
                f"  eff={op['effective_time_s']}s"
                f"  stawka={op['rate_zl_h']} zł/h  koszt={op['cost_zl']:.4f} zł"
            )

        # Materials
        L.append("  Materiały:")
        for m in item["materials"]:
            src = f"[{m['price_source']}]" if m["price_source"] else ""
            L.append(
                f"    • {m['material_name']:<32}  {m['quantity_gross']} {m['unit']}"
                f"  × {m['price_per_unit']:.4f} zł/{m['unit']}"
                f"  = {m['cost_zl']:.4f} zł  {src}"
            )

        # Outside services
        if item["outside_services"]:
            L.append("  Usługi zewnętrzne:")
            for s in item["outside_services"]:
                L.append(
                    f"    • {s['service_name']:<32}  {s['quantity']} {s['unit']}"
                    f"  × {s['price_per_unit']:.4f} zł/{s['unit']}"
                    f"  = {s['cost_zl']:.4f} zł"
                )

        # Cost summary
        L += [
            f"  ── Koszt materiału:       {item['material_zl']:>10.2f} zł",
            f"  ── Koszt operacji:        {item['operations_zl']:>10.2f} zł",
            f"  ── Usługi zewnętrzne:     {item['outside_services_zl']:>10.2f} zł",
            f"  ── Pakowanie:             {item['packaging_zl']:>10.2f} zł",
            f"  ── Korekty:               {item['adjustment_zl']:>10.2f} zł",
            f"  ══ RAZEM:                 {item['total_zl']:>10.2f} zł"
            f"  ({item['unit_cost_zl']:.4f} zł/szt.)",
        ]

        # Assumptions
        if item["assumptions"]:
            L.append("  Założenia:")
            for a in item["assumptions"]:
                status = "OK " if a["confirmed"] else "???"
                L.append(
                    f"    [{status}] {a['field_name']} = {a['assumed_value']}"
                    f" — {a['reason']}"
                )

        # Item-level risks
        if item["risks"]:
            L.append("  RYZYKA:")
            for r in item["risks"]:
                L.append(f"    !!! {r}")

    # Footer
    L += [
        "",
        sep,
        f"ŁĄCZNY KOSZT KALKULACJI:  {card['total_cost_zl']:.2f} zł",
    ]
    if card["global_risks"]:
        L.append("OSTRZEŻENIA GLOBALNE:")
        for r in card["global_risks"]:
            L.append(f"  !!! {r}")
    if card["tech_notes"]:
        L += ["", f"Uwagi techniczne:  {card['tech_notes']}"]
    if card["commercial_notes"]:
        L += [f"Uwagi handlowe:    {card['commercial_notes']}"]
    L.append(sep)

    return "\n".join(L)
