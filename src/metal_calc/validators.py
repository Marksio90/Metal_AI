from __future__ import annotations

from metal_calc.exceptions import DomainValidationError
from metal_calc.materials import normalize_material
from metal_calc.models import MissingInformation, RFQInput


def detect_missing_information(rfq: RFQInput) -> MissingInformation:
    missing: list[str] = []
    if not rfq.customer.name.strip():
        missing.append("customer.name")
    if rfq.quantity_break.quantity <= 0:
        missing.append("quantity_break.quantity")
    if normalize_material(rfq.material.material_code) == "unknown_material":
        missing.append("material.material_code")
    if rfq.part.mass_kg is None:
        missing.append("part.mass_kg")
    return MissingInformation(fields=missing)


def validate_rfq(rfq: RFQInput) -> None:
    missing = detect_missing_information(rfq)
    if missing.fields:
        raise DomainValidationError(f"Missing required information: {', '.join(missing.fields)}")
