"""
Material price engine — four source tiers with date validity and provenance.

Priority order (highest to lowest):
  1. PROCUREMENT_QUERY  — confirmed quote from purchasing dept
  2. ERP_LAST_MOVEMENT  — last purchase movement from ERP
  3. MONTHLY_LIST       — periodic price list (refreshed monthly)
  4. TEMPORARY_RULE     — fallback estimate; MUST be flagged in assumptions_log
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

from metal_calc.models.enums import MaterialFamily, MaterialForm, PriceSource


@dataclass
class MaterialPrice:
    material_family: MaterialFamily
    material_grade: str              # e.g. "S235JR", "304", "DC01"
    form: MaterialForm
    unit: str                        # "kg", "mb", "m2"
    price_per_unit: float            # zł / unit, net of VAT
    source: PriceSource
    valid_from: datetime.date
    valid_to: Optional[datetime.date]  # None = open-ended
    source_ref: str = ""             # document/email/ERP ref for audit
    confirmed: bool = True           # False only for TEMPORARY_RULE

    def is_valid_on(self, date: datetime.date) -> bool:
        if date < self.valid_from:
            return False
        if self.valid_to is not None and date > self.valid_to:
            return False
        return True

    def source_label(self) -> str:
        labels = {
            PriceSource.MONTHLY_LIST: "Cennik miesięczny",
            PriceSource.ERP_LAST_MOVEMENT: "Ostatni ruch ERP",
            PriceSource.PROCUREMENT_QUERY: "Zapytanie do zaopatrzenia",
            PriceSource.TEMPORARY_RULE: "Reguła tymczasowa (wymaga potwierdzenia)",
        }
        return labels.get(self.source, self.source.value)


# ---------------------------------------------------------------------------
# In-memory price registry
# ---------------------------------------------------------------------------

class MaterialPriceRegistry:
    """
    Stores material prices and resolves the best valid price for a given
    material on a specific date following the priority rules above.
    """

    _PRIORITY: dict[PriceSource, int] = {
        PriceSource.PROCUREMENT_QUERY: 1,
        PriceSource.ERP_LAST_MOVEMENT: 2,
        PriceSource.MONTHLY_LIST: 3,
        PriceSource.TEMPORARY_RULE: 4,
    }

    def __init__(self) -> None:
        self._entries: list[MaterialPrice] = []

    def add(self, price: MaterialPrice) -> None:
        self._entries.append(price)

    def resolve(
        self,
        material_family: MaterialFamily,
        material_grade: str,
        form: MaterialForm,
        on_date: datetime.date,
    ) -> MaterialPrice | None:
        """
        Return the highest-priority valid price entry for the given material.
        Returns None if no matching entry exists (caller must flag as missing data).
        """
        candidates = [
            e for e in self._entries
            if (
                e.material_family == material_family
                and e.material_grade == material_grade
                and e.form == form
                and e.is_valid_on(on_date)
            )
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda e: self._PRIORITY[e.source])

    def all_for_family(self, family: MaterialFamily) -> list[MaterialPrice]:
        return [e for e in self._entries if e.material_family == family]


# ---------------------------------------------------------------------------
# Outside-service price registry (cynkowanie, chromowanie, etc.)
# ---------------------------------------------------------------------------

@dataclass
class OutsideServicePrice:
    service_type: str             # matches OutsideServiceType value
    subtype: str                  # e.g. "bebn", "trawers" for galvanizing
    unit: str                     # "kg", "dm2", "szt"
    price_per_unit: float
    supplier: str
    valid_from: datetime.date
    valid_to: Optional[datetime.date]
    source_ref: str = ""
    confirmed: bool = True

    def is_valid_on(self, date: datetime.date) -> bool:
        if date < self.valid_from:
            return False
        if self.valid_to is not None and date > self.valid_to:
            return False
        return True


class OutsideServiceRegistry:
    def __init__(self) -> None:
        self._entries: list[OutsideServicePrice] = []

    def add(self, price: OutsideServicePrice) -> None:
        self._entries.append(price)

    def resolve(
        self,
        service_type: str,
        subtype: str,
        on_date: datetime.date,
    ) -> OutsideServicePrice | None:
        candidates = [
            e for e in self._entries
            if (
                e.service_type == service_type
                and e.subtype == subtype
                and e.is_valid_on(on_date)
            )
        ]
        if not candidates:
            return None
        return candidates[-1]  # last-added wins among equals
