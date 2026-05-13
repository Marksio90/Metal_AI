"""
RFQ intake — completeness check and status logic.

The check runs before any calculation begins.
If critical fields are missing the RFQ status is set to MISSING_DATA
and no calculation is allowed to start.

Critical fields are those without which a cost cannot be calculated at all.
Advisory fields produce a warning but do not block calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metal_calc.models.enums import ProductFamily, RFQStatus


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

CRITICAL_COMMON = [
    "client",
    "quantity",
    "product_family",
    "material_family",
    "material_grade",
    "finish",
]

CRITICAL_BY_FAMILY: dict[str, list[str]] = {
    ProductFamily.WIRE.value: [
        "wire_diameter_mm",
        "unit_mass_kg",
    ],
    ProductFamily.SHEET.value: [
        "thickness_mm",
        "unit_mass_kg",
        "nesting_sheets_count",
    ],
    ProductFamily.TUBE.value: [
        "tube_od_mm",
        "wall_thickness_mm",
        "length_mm",
        "unit_mass_kg",
    ],
    ProductFamily.MESH.value: [
        "wire_diameter_mm",
        "mesh_width_mm",
        "mesh_height_mm",
        "unit_mass_kg",
    ],
    ProductFamily.STRUCTURE.value: [
        "component_list",
        "assembly_description",
    ],
}

ADVISORY_COMMON = [
    "salesperson",
    "rfq_subject",
    "drawing_reference",
    "delivery_date_requested",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class IntakeCheckResult:
    status: RFQStatus
    missing_critical: list[str] = field(default_factory=list)
    missing_advisory: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ready_for_calculation(self) -> bool:
        return self.status == RFQStatus.READY_FOR_CALC

    def summary(self) -> dict:
        return {
            "status": self.status.value,
            "ready_for_calculation": self.ready_for_calculation,
            "missing_critical": self.missing_critical,
            "missing_advisory": self.missing_advisory,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

def check_rfq_completeness(data: dict[str, Any]) -> IntakeCheckResult:
    """
    Validate an RFQ data dict against critical and advisory field lists.

    A field is considered present if it exists in `data` and is not None,
    not an empty string, and not an empty list.
    """

    def is_present(key: str) -> bool:
        v = data.get(key)
        if v is None:
            return False
        if isinstance(v, str) and not v.strip():
            return False
        if isinstance(v, (list, dict)) and not v:
            return False
        return True

    missing_critical: list[str] = []
    missing_advisory: list[str] = []
    warnings: list[str] = []

    for f in CRITICAL_COMMON:
        if not is_present(f):
            missing_critical.append(f)

    family = data.get("product_family")
    if family and isinstance(family, str):
        family_fields = CRITICAL_BY_FAMILY.get(family)
        if family_fields is None:
            warnings.append(
                f"product_family '{family}' not recognised — family-specific checks skipped"
            )
        else:
            for f in family_fields:
                if not is_present(f):
                    missing_critical.append(f)

    for f in ADVISORY_COMMON:
        if not is_present(f):
            missing_advisory.append(f)

    # Quantity must be a positive integer
    qty = data.get("quantity")
    if qty is not None:
        try:
            if int(qty) <= 0:
                missing_critical.append("quantity_must_be_positive")
        except (ValueError, TypeError):
            missing_critical.append("quantity_must_be_numeric")

    # Finish validation
    finish = data.get("finish", "")
    if isinstance(finish, str) and finish.strip().lower() == "nieokreślone":
        warnings.append("finish is 'nieokreślone' — coating cost cannot be calculated")

    if missing_critical:
        status = RFQStatus.MISSING_DATA
    else:
        status = RFQStatus.READY_FOR_CALC

    return IntakeCheckResult(
        status=status,
        missing_critical=missing_critical,
        missing_advisory=missing_advisory,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Salesperson response card builder
# ---------------------------------------------------------------------------

def build_missing_data_reply(
    rfq_number: str,
    client: str,
    check_result: IntakeCheckResult,
) -> str:
    """
    Generate a Polish-language reply text requesting missing data from the client.
    The sales person sends this; the system creates the draft.
    """
    lines = [
        f"Szanowni Państwo,",
        f"",
        f"Dziękujemy za przesłanie zapytania ofertowego nr {rfq_number}.",
        f"Aby przygotować dokładną wycenę, potrzebujemy następujących informacji:",
        f"",
    ]

    field_labels = {
        "quantity": "Ilość sztuk",
        "product_family": "Rodzaj wyrobu (drut, blacha, rura, siatka, konstrukcja)",
        "material_family": "Rodzaj materiału (stal czarna, nierdzewna, ocynkowana, aluminium, itp.)",
        "material_grade": "Gatunek materiału (np. S235JR, DC01, 304)",
        "finish": "Wykończenie / powłoka (malowanie proszkowe, cynkowanie, surowe, itp.)",
        "wire_diameter_mm": "Średnica drutu [mm]",
        "unit_mass_kg": "Masa jednostkowa wyrobu [kg]",
        "thickness_mm": "Grubość blachy [mm]",
        "nesting_sheets_count": "Liczba arkuszy (lub wymiary detalu do nestingu)",
        "tube_od_mm": "Średnica zewnętrzna rury [mm]",
        "wall_thickness_mm": "Grubość ścianki rury [mm]",
        "length_mm": "Długość [mm]",
        "mesh_width_mm": "Szerokość siatki [mm]",
        "mesh_height_mm": "Wysokość siatki [mm]",
        "component_list": "Lista podzespołów / detali składowych",
        "assembly_description": "Opis montażu",
        "quantity_must_be_positive": "Ilość musi być liczbą całkowitą większą od zera",
        "quantity_must_be_numeric": "Ilość musi być podana jako liczba",
    }

    for f in check_result.missing_critical:
        label = field_labels.get(f, f)
        lines.append(f"  • {label}")

    lines += [
        f"",
        f"Z wyrazami szacunku,",
        f"Dział Sprzedaży",
    ]
    return "\n".join(lines)
