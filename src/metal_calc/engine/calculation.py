"""
Deterministic calculation engine.

Formula set (frozen — changes require explicit version bump):

    stawka_zl_s  = price_zl_h / 3600
    czas_eff_s   = setup_sec + (cycle_sec * quantity) + extra_sec
    koszt_op     = stawka_zl_s * czas_eff_s

    koszt_poz    = koszt_materialu
                 + sum(koszt_op for each operation)
                 + koszt_uslug_zewn
                 + koszt_pakowania  (if separate outside the routing)
                 + sum(adjustments recorded in assumptions_log)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from metal_calc.data.machine_rates_2025 import MACHINE_RATES, MachineRate, get_machine
from metal_calc.models.enums import PriceProfile


# ---------------------------------------------------------------------------
# Operation line
# ---------------------------------------------------------------------------

@dataclass
class OperationLine:
    """Single operation to be costed."""
    operation_name: str          # human label, e.g. "Laser Fiber do blach"
    machine_name: str            # key in MACHINE_RATES
    setup_sec: float             # one-off per batch
    cycle_sec: float             # per piece
    quantity: int
    extra_sec: float = 0.0       # rounding allowance, scrap correction, etc.
    note: str = ""

    # resolved at cost time
    _rate_used: float | None = field(default=None, init=False, repr=False)

    @property
    def machine_rate(self) -> MachineRate:
        return get_machine(self.machine_name)

    def effective_time_s(self) -> float:
        """czas_efektywny_s = setup_sec + cycle_sec * quantity + extra_sec"""
        return self.setup_sec + self.cycle_sec * self.quantity + self.extra_sec

    def cost_zl(self, profile: PriceProfile) -> float:
        """koszt_operacji = stawka_zl_s * czas_efektywny_s"""
        rate_s = self.machine_rate.rate_zl_s(profile.value)
        self._rate_used = rate_s
        return rate_s * self.effective_time_s()

    def cost_zl_per_piece(self, profile: PriceProfile) -> float:
        return self.cost_zl(profile) / self.quantity if self.quantity else 0.0


# ---------------------------------------------------------------------------
# Material line
# ---------------------------------------------------------------------------

@dataclass
class MaterialLine:
    material_name: str
    unit: str                    # "kg", "mb", "szt", "m2"
    quantity_net: float          # net consumption per batch
    scrap_factor: float = 1.0    # 1.05 = 5% scrap; must be >= 1.0
    price_per_unit: float = 0.0  # zł / unit
    price_source: str = ""
    note: str = ""

    @property
    def quantity_gross(self) -> float:
        return self.quantity_net * self.scrap_factor

    def cost_zl(self) -> float:
        return self.quantity_gross * self.price_per_unit


# ---------------------------------------------------------------------------
# Outside-service line
# ---------------------------------------------------------------------------

@dataclass
class OutsideServiceLine:
    service_name: str
    service_type: str            # e.g. "cynkowanie_bebn", "chromowanie"
    unit: str                    # "kg", "dm2", "szt"
    quantity: float
    price_per_unit: float
    price_source: str = ""
    note: str = ""

    def cost_zl(self) -> float:
        return self.quantity * self.price_per_unit


# ---------------------------------------------------------------------------
# Assumption entry (audit trail)
# ---------------------------------------------------------------------------

@dataclass
class AssumptionEntry:
    field_name: str
    assumed_value: str
    reason: str
    confirmed: bool = False


# ---------------------------------------------------------------------------
# Quote item (one product line in a quotation)
# ---------------------------------------------------------------------------

@dataclass
class QuoteItem:
    item_name: str
    product_family: str
    quantity: int
    operations: list[OperationLine] = field(default_factory=list)
    materials: list[MaterialLine] = field(default_factory=list)
    outside_services: list[OutsideServiceLine] = field(default_factory=list)
    assumptions: list[AssumptionEntry] = field(default_factory=list)
    packaging_cost_zl: float = 0.0    # flat rate if not in routing
    adjustment_zl: float = 0.0        # explicitly logged adjustments

    def total_operation_cost_zl(self, profile: PriceProfile) -> float:
        return sum(op.cost_zl(profile) for op in self.operations)

    def total_material_cost_zl(self) -> float:
        return sum(m.cost_zl() for m in self.materials)

    def total_outside_service_cost_zl(self) -> float:
        return sum(s.cost_zl() for s in self.outside_services)

    def total_cost_zl(self, profile: PriceProfile) -> float:
        """
        koszt_pozycji = koszt_materiału
                      + suma(kosztów_operacji)
                      + koszt_usług_zewnętrznych
                      + pakowanie
                      + korekty z założeń
        """
        return (
            self.total_material_cost_zl()
            + self.total_operation_cost_zl(profile)
            + self.total_outside_service_cost_zl()
            + self.packaging_cost_zl
            + self.adjustment_zl
        )

    def unit_cost_zl(self, profile: PriceProfile) -> float:
        return self.total_cost_zl(profile) / self.quantity if self.quantity else 0.0

    def has_unconfirmed_assumptions(self) -> bool:
        return any(not a.confirmed for a in self.assumptions)

    def cost_breakdown(self, profile: PriceProfile) -> dict:
        return {
            "material_zl": round(self.total_material_cost_zl(), 4),
            "operations_zl": round(self.total_operation_cost_zl(profile), 4),
            "outside_services_zl": round(self.total_outside_service_cost_zl(), 4),
            "packaging_zl": round(self.packaging_cost_zl, 4),
            "adjustment_zl": round(self.adjustment_zl, 4),
            "total_zl": round(self.total_cost_zl(profile), 4),
            "unit_cost_zl": round(self.unit_cost_zl(profile), 4),
            "quantity": self.quantity,
            "price_profile": profile.label(),
            "unconfirmed_assumptions": self.has_unconfirmed_assumptions(),
        }


# ---------------------------------------------------------------------------
# Quote header
# ---------------------------------------------------------------------------

@dataclass
class Quote:
    quote_number: str
    version: int
    client: str
    salesperson: str
    rfq_reference: str
    price_profile: PriceProfile
    calc_date: str               # ISO date string
    valid_until: str             # ISO date string
    tech_notes: str = ""
    commercial_notes: str = ""
    items: list[QuoteItem] = field(default_factory=list)

    def total_cost_zl(self) -> float:
        return sum(item.total_cost_zl(self.price_profile) for item in self.items)

    def has_any_unconfirmed_assumptions(self) -> bool:
        return any(item.has_unconfirmed_assumptions() for item in self.items)

    def summary(self) -> dict:
        return {
            "quote_number": self.quote_number,
            "version": self.version,
            "client": self.client,
            "salesperson": self.salesperson,
            "rfq_reference": self.rfq_reference,
            "price_profile": self.price_profile.label(),
            "calc_date": self.calc_date,
            "valid_until": self.valid_until,
            "total_cost_zl": round(self.total_cost_zl(), 4),
            "items": [
                {
                    "name": item.item_name,
                    **item.cost_breakdown(self.price_profile),
                }
                for item in self.items
            ],
            "risk_flags": {
                "unconfirmed_assumptions": self.has_any_unconfirmed_assumptions(),
            },
            "tech_notes": self.tech_notes,
            "commercial_notes": self.commercial_notes,
        }
