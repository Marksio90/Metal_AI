from __future__ import annotations

SUPPORTED_MATERIALS = {
    "s235": "S235",
    "s355": "S355",
    "stainless_steel": "stainless steel",
    "aluminum": "aluminum",
    "unknown_material": "unknown material",
}


def normalize_material(material_code: str | None) -> str:
    if not material_code:
        return "unknown_material"
    key = material_code.strip().lower().replace(" ", "_")
    return key if key in SUPPORTED_MATERIALS else "unknown_material"
