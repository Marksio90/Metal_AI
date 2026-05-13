"""
Metal Calc CLI — interaktywne narzędzie kalkulacji dla handlowca/operatora.

Uruchomienie:
    python -m metal_calc.cli
    lub (po instalacji):
    metal-calc
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from metal_calc.data.machine_rates_2025 import MACHINE_RATES
from metal_calc.data.routing_templates import MESH, SHEET, STRUCTURE, TUBE, WIRE
from metal_calc.engine.calc_form import CalcForm
from metal_calc.engine.calculation import MaterialLine, OperationLine, Quote, QuoteItem
from metal_calc.engine.email_generator import build_full_salesperson_package
from metal_calc.models.enums import OperationType, PriceProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "=" * 64
SEP2 = "-" * 64

FAMILIES = {
    "1": ("DRUT (Wire)", WIRE),
    "2": ("BLACHA (Sheet)", SHEET),
    "3": ("RURA/PROFIL (Tube)", TUBE),
    "4": ("SIATKA (Mesh)", MESH),
    "5": ("KONSTRUKCJA (Structure)", STRUCTURE),
}

PROFILES = {
    "0": PriceProfile.MARGIN_0,
    "20": PriceProfile.MARGIN_20,
    "45": PriceProfile.MARGIN_45,
}


def _ask(prompt: str, default: str = "") -> str:
    if default:
        raw = input(f"{prompt} [{default}]: ").strip()
        return raw if raw else default
    raw = input(f"{prompt}: ").strip()
    return raw


def _ask_float(prompt: str, default: float | None = None) -> float:
    while True:
        raw = _ask(prompt, str(default) if default is not None else "")
        try:
            return float(raw)
        except ValueError:
            print("  ⚠  Wprowadź liczbę (np. 3.5).")


def _ask_int(prompt: str, default: int | None = None) -> int:
    while True:
        raw = _ask(prompt, str(default) if default is not None else "")
        try:
            val = int(raw)
            if val <= 0:
                print("  ⚠  Wartość musi być > 0.")
                continue
            return val
        except ValueError:
            print("  ⚠  Wprowadź liczbę całkowitą.")


def _choose(prompt: str, options: dict[str, str]) -> str:
    """Display numbered menu and return user's key."""
    for key, label in options.items():
        print(f"  {key}) {label}")
    while True:
        raw = input(f"{prompt}: ").strip()
        if raw in options:
            return raw
        print(f"  ⚠  Wybierz spośród: {', '.join(options)}")


def _yn(prompt: str, default: bool = False) -> bool:
    hint = " [T/n]" if default else " [t/N]"
    raw = input(f"{prompt}{hint}: ").strip().lower()
    if not raw:
        return default
    return raw in ("t", "tak", "y", "yes")


def _print_sep(char: str = "=") -> None:
    print(char * 64)


# ---------------------------------------------------------------------------
# Quote header
# ---------------------------------------------------------------------------

def _collect_quote_header() -> dict:
    print()
    _print_sep()
    print("NAGŁÓWEK OFERTY")
    _print_sep()
    today = date.today().isoformat()
    valid = (date.today() + timedelta(days=30)).isoformat()

    number = _ask("Numer oferty (np. OF-2025-001)", f"OF-{date.today().year}-001")
    version = _ask_int("Wersja", 1)
    client = _ask("Klient")
    salesperson = _ask("Handlowiec")
    rfq = _ask("Numer RFQ (opcjonalnie)", "")
    calc_date = _ask("Data kalkulacji", today)
    valid_until = _ask("Ważna do", valid)

    print()
    print("Profil cenowy:")
    p_key = _choose("Wybierz", {"0": "Marża 0%", "20": "Marża 20%", "45": "Marża 45%"})
    profile = PROFILES[p_key]

    tech_notes = _ask("Uwagi techniczne (opcjonalnie)", "")
    commercial_notes = _ask("Uwagi handlowe (opcjonalnie)", "")

    return dict(
        quote_number=number,
        version=version,
        client=client,
        salesperson=salesperson,
        rfq_reference=rfq,
        price_profile=profile,
        calc_date=calc_date,
        valid_until=valid_until,
        tech_notes=tech_notes or None,
        commercial_notes=commercial_notes or None,
    )


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _collect_operations(form: CalcForm) -> None:
    """Interactive loop — fill operations for all template steps."""
    template = form.template
    print()
    print("OPERACJE")
    print(SEP2)
    print("Dostępne kroki wg szablonu (M=obowiązkowy, O=opcjonalny):")

    skippable_mandatory = []   # mandatory steps with no candidate machines (e.g. NESTING)

    for step in template.steps:
        flag = "M" if step.mandatory else "O"
        machines_str = ", ".join(step.candidate_machines) if step.candidate_machines else "— brak (dane wejściowe)"
        print(f"  [{flag}] {step.op_type.value}  →  {machines_str}")
        if step.mandatory and not step.candidate_machines:
            skippable_mandatory.append(step)

    if skippable_mandatory:
        print()
        for step in skippable_mandatory:
            print(f"  ℹ  Krok '{step.op_type.value}' jest obowiązkowy, ale nie wymaga maszyny")
            print("     (dane wejściowe — np. wynik nestingu). Pomijam w formularzu.")

    print()

    for step in template.steps:
        if not step.candidate_machines:
            continue   # no machine to choose — skip

        flag = "(obowiązkowy)" if step.mandatory else "(opcjonalny — Enter aby pominąć)"
        print(f"Operacja: {step.op_type.value}  {flag}")

        if not step.mandatory:
            if not _yn(f"  Czy dodać operację '{step.op_type.value}'?", False):
                continue

        # Choose machine
        machines = list(step.candidate_machines)
        if len(machines) == 1:
            machine = machines[0]
            print(f"  Maszyna: {machine} (jedyna dostępna)")
        else:
            print("  Dostępne maszyny:")
            opts = {str(i + 1): m for i, m in enumerate(machines)}
            m_key = _choose("  Wybierz maszynę", opts)
            machine = opts[m_key]

        rate = MACHINE_RATES[machine].price_20pct_zl_h
        print(f"  Stawka P20: {rate} zł/h  ({rate/3600:.5f} zł/s)")

        setup = _ask_float("  Czas nastawniczy setup_sec [s]", 0.0)
        cycle = _ask_float("  Takt cycle_sec [s/szt]", 0.0)

        try:
            form.fill_operation(step.op_type, machine,
                                setup_sec=setup, cycle_sec=cycle)
        except ValueError as exc:
            print(f"  ⚠  Błąd: {exc}")
        print()


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def _collect_materials(form: CalcForm) -> None:
    print("MATERIAŁY")
    print(SEP2)
    while True:
        mat_name = _ask("Nazwa materiału (Enter = koniec)")
        if not mat_name:
            if not form._materials:
                print("  ⚠  Wymagany co najmniej jeden materiał.")
                continue
            break
        unit = _ask("  Jednostka (kg/mb/szt/m2)", "kg")
        qty_net = _ask_float("  Ilość netto")
        scrap = _ask_float("  Współczynnik odpadów (np. 1.02)", 1.0)
        price = _ask_float("  Cena/jednostkę [zł]", 0.0)
        source = _ask("  Źródło ceny (opcjonalnie)", "")
        form.fill_material(mat_name, unit=unit, quantity_net=qty_net,
                           scrap_factor=scrap, price_per_unit=price,
                           price_source=source)
        print(f"  ✓ Dodano: {mat_name}  ({qty_net} × {scrap} × {price:.4f} zł = "
              f"{qty_net * scrap * price:.2f} zł)")
        print()


# ---------------------------------------------------------------------------
# Outside services
# ---------------------------------------------------------------------------

def _collect_outside_services(form: CalcForm) -> None:
    if not _yn("Czy dodać usługi zewnętrzne (cynkowanie, lakierowanie itp.)?", False):
        return
    print("USŁUGI ZEWNĘTRZNE")
    print(SEP2)
    while True:
        svc_name = _ask("Nazwa usługi (Enter = koniec)")
        if not svc_name:
            break
        svc_type = _ask("  Typ usługi (np. cynkowanie_bebn)", svc_name.lower().replace(" ", "_"))
        unit = _ask("  Jednostka (kg/mb/szt/m2)", "kg")
        qty = _ask_float("  Ilość")
        price = _ask_float("  Cena/jednostkę [zł]")
        form.fill_outside_service(
            service_name=svc_name,
            service_type=svc_type,
            unit=unit,
            quantity=qty,
            price_per_unit=price,
        )
        print(f"  ✓ Dodano: {svc_name}  ({qty} × {price:.4f} zł = {qty * price:.2f} zł)")
        print()


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

def _collect_assumptions(form: CalcForm) -> None:
    if not _yn("Czy dodać założenia kalkulacyjne?", False):
        return
    print("ZAŁOŻENIA")
    print(SEP2)
    while True:
        field_name = _ask("Pole założenia (np. finish, material_grade) — Enter=koniec")
        if not field_name:
            break
        value = _ask("  Przyjęta wartość")
        reason = _ask("  Powód założenia")
        confirmed = _yn("  Potwierdzone przez klienta?", False)
        form.add_assumption(field_name, value, reason, confirmed=confirmed)
        status = "✓ potwierdzone" if confirmed else "⚠ NIEpotwierdzone"
        print(f"  [{status}] {field_name} = {value}")
        print()


# ---------------------------------------------------------------------------
# Build one item
# ---------------------------------------------------------------------------

def _build_item(item_num: int) -> QuoteItem | None:
    print()
    _print_sep()
    print(f"POZYCJA {item_num}")
    _print_sep()

    # Family
    print("Rodzina wyrobu:")
    fam_key = _choose("Wybierz", {k: v[0] for k, v in FAMILIES.items()})
    _, template = FAMILIES[fam_key]

    item_name = _ask("Nazwa pozycji (np. 'Drut fi5 S235JR')")
    qty = _ask_int("Ilość [szt]")

    form = CalcForm.from_template(template, item_name=item_name, quantity=qty)

    _collect_operations(form)
    _collect_materials(form)
    _collect_outside_services(form)

    pack = _ask_float("Koszt pakowania [zł] (0 = brak)", 0.0)
    adj = _ask_float("Korekta (rabat: ujemna, dopłata: dodatnia) [zł]", 0.0)
    form.packaging_cost_zl = pack
    form.adjustment_zl = adj

    _collect_assumptions(form)

    errors = form.validate()
    if errors:
        print()
        print("⚠  Błędy walidacji:")
        for e in errors:
            print(f"   • {e}")
        if not _yn("Mimo błędów — zbudować pozycję?", False):
            return None

    return form.build_quote_item()


# ---------------------------------------------------------------------------
# Preview cost breakdown
# ---------------------------------------------------------------------------

def _preview_item(item: QuoteItem, profile: PriceProfile) -> None:
    bd = item.cost_breakdown(profile)
    print()
    print(f"  Pozycja: {item.item_name}  (qty={item.quantity})")
    print(f"    Materiał:           {bd['material_zl']:>10.2f} zł")
    print(f"    Operacje:           {bd['operations_zl']:>10.2f} zł")
    if bd["outside_services_zl"]:
        print(f"    Usługi zewnętrzne:  {bd['outside_services_zl']:>10.2f} zł")
    if bd["packaging_zl"]:
        print(f"    Pakowanie:          {bd['packaging_zl']:>10.2f} zł")
    if bd["adjustment_zl"]:
        print(f"    Korekta:            {bd['adjustment_zl']:>10.2f} zł")
    print(f"    ── RAZEM:           {bd['total_zl']:>10.2f} zł")
    print(f"    ── Jedn./szt.:      {bd['unit_cost_zl']:>10.4f} zł/szt.")
    if item.has_unconfirmed_assumptions():
        print("    ⚠  Zawiera niezatwierdzone założenia!")


# ---------------------------------------------------------------------------
# Output: save to file
# ---------------------------------------------------------------------------

def _save_package(pkg: dict, quote_number: str) -> None:
    slug = quote_number.replace("/", "-").replace(" ", "_")
    fname = f"{slug}_pakiet.txt"
    with open(fname, "w", encoding="utf-8") as fh:
        fh.write("TEMAT MAILA\n")
        fh.write("=" * 64 + "\n")
        fh.write(pkg["email_subject"] + "\n\n")
        fh.write("TREŚĆ MAILA (klient)\n")
        fh.write("=" * 64 + "\n")
        fh.write(pkg["email_body"] + "\n\n")
        if pkg["risk_note"]:
            fh.write("NOTATKA WEWNĘTRZNA\n")
            fh.write("=" * 64 + "\n")
            fh.write(pkg["risk_note"] + "\n\n")
        fh.write("KARTA KALKULACJI (internal)\n")
        fh.write("=" * 64 + "\n")
        fh.write(pkg["sales_card_text"] + "\n")
    print(f"  ✓ Zapisano do pliku: {fname}")


# ---------------------------------------------------------------------------
# Main new-quote flow
# ---------------------------------------------------------------------------

def _new_quote_flow() -> None:
    header = _collect_quote_header()

    items: list[QuoteItem] = []
    while True:
        item = _build_item(len(items) + 1)
        if item is not None:
            items.append(item)
            print(f"  ✓ Dodano pozycję: {item.item_name}")
        if not _yn("Dodać kolejną pozycję?", False):
            break

    if not items:
        print("Brak pozycji — anulowanie.")
        return

    quote = Quote(items=items, **header)

    # Summary
    print()
    _print_sep()
    print("PODSUMOWANIE OFERTY")
    _print_sep()
    print(f"  Oferta:   {quote.quote_number}  (wer. {quote.version})")
    print(f"  Klient:   {quote.client}")
    print(f"  Profil:   {quote.price_profile.label()}")
    for item in items:
        _preview_item(item, quote.price_profile)
    print()
    print(f"  ŁĄCZNY KOSZT:  {quote.total_cost_zl():.2f} zł")
    print()

    # Output options
    print("Co chcesz zrobić z wynikiem?")
    print("  1) Wyświetl kartę kalkulacji")
    print("  2) Wyświetl szkic maila do klienta")
    print("  3) Wyświetl cały pakiet (karta + mail)")
    print("  4) Zapisz pakiet do pliku")
    print("  5) Powrót do menu głównego")

    sender_name = _ask("Imię i nazwisko handlowca (podpis maila)", quote.salesperson)
    sender_company = _ask("Firma (podpis maila)", "Metal AI Sp. z o.o.")

    pkg = build_full_salesperson_package(
        quote,
        sender_name=sender_name,
        sender_company=sender_company,
    )

    actions_done = False
    while not actions_done:
        choice = _ask("Wybierz (1-5)", "5")
        if choice == "1":
            print()
            print(pkg["sales_card_text"])
        elif choice == "2":
            print()
            print(f"TEMAT: {pkg['email_subject']}")
            print(SEP2)
            print(pkg["email_body"])
            if pkg["risk_note"]:
                print()
                print(pkg["risk_note"])
        elif choice == "3":
            print()
            print(f"TEMAT: {pkg['email_subject']}")
            print(SEP2)
            print(pkg["email_body"])
            if pkg["risk_note"]:
                print()
                print(pkg["risk_note"])
            print()
            print(pkg["sales_card_text"])
        elif choice == "4":
            _save_package(pkg, quote.quote_number)
        elif choice == "5":
            actions_done = True
        else:
            print("  ⚠  Wybierz 1–5.")
            continue
        if choice != "5":
            actions_done = not _yn("Wybrać inną opcję?", False)


# ---------------------------------------------------------------------------
# Quick cost estimator (single operation, no full quote)
# ---------------------------------------------------------------------------

def _quick_estimate_flow() -> None:
    print()
    _print_sep()
    print("SZYBKA WYCENA OPERACJI")
    _print_sep()
    print("Dostępne maszyny:")
    machines = sorted(MACHINE_RATES.keys())
    for i, name in enumerate(machines, 1):
        m = MACHINE_RATES[name]
        print(f"  {i:>2}) {name:<42} P0={m.price_0pct_zl_h:>5} / P20={m.price_20pct_zl_h:>5} / P45={m.price_45pct_zl_h:>5} zł/h")

    machine_idx = _ask_int("Wybierz numer maszyny") - 1
    if machine_idx < 0 or machine_idx >= len(machines):
        print("  ⚠  Nieprawidłowy numer.")
        return
    machine = machines[machine_idx]
    m = MACHINE_RATES[machine]

    print()
    print(f"Maszyna: {machine}")
    print(f"  P0={m.price_0pct_zl_h} / P20={m.price_20pct_zl_h} / P45={m.price_45pct_zl_h} zł/h")

    p_key = _choose("Profil cenowy", {"0": "Marża 0%", "20": "Marża 20%", "45": "Marża 45%"})
    profile = PROFILES[p_key]

    qty = _ask_int("Ilość szt.")
    setup = _ask_float("Setup [s]", 0.0)
    cycle = _ask_float("Takt [s/szt]", 0.0)

    eff = setup + cycle * qty
    rate_s = m.rate_zl_s(profile.value)
    cost = rate_s * eff

    print()
    print(f"  Czas efektywny:  {eff:.1f} s  = {eff/60:.2f} min")
    print(f"  Stawka:          {rate_s*3600:.2f} zł/h  ({rate_s:.6f} zł/s)")
    print(f"  Koszt operacji:  {cost:.2f} zł  ({cost/qty:.4f} zł/szt.)")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    _print_sep()
    print("  METAL CALC — Kalkulator Kosztów Produkcji")
    print("  Wersja danych: Cennik 2025-04-07")
    _print_sep()

    while True:
        print()
        print("MENU GŁÓWNE")
        print("  1) Nowa wycena (pełny formularz)")
        print("  2) Szybka wycena operacji")
        print("  0) Wyjście")
        choice = _ask("Wybierz", "1")

        if choice == "1":
            try:
                _new_quote_flow()
            except KeyboardInterrupt:
                print("\n  (przerwano)")
        elif choice == "2":
            try:
                _quick_estimate_flow()
            except KeyboardInterrupt:
                print("\n  (przerwano)")
        elif choice == "0":
            print("Do widzenia!")
            sys.exit(0)
        else:
            print("  ⚠  Wybierz 0, 1 lub 2.")


if __name__ == "__main__":
    main()
