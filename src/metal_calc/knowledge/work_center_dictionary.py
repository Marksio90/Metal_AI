"""Work center (brygada) dictionary and operation-to-work-center preferences."""

from __future__ import annotations

KNOWN_WORK_CENTERS = [
    "LASER",
    "LASER DO RUR",
    "PAKOWANIE",
    "PRASY",
    "GIĘTARKA SAFAN",
    "GIĘTARKI CNC",
    "SPAWALNIA",
    "PROŚCIARKI",
    "PRASY MIMOŚRODOWE",
    "ZGRZEWARKI",
    "ZGRZEWARKI AUTOMATYCZNE",
    "MONTAŻ",
    "ROBOT",
    "WYKRAWARKA E5",
    "PRASA AUTOMATYCZNA 100t",
    "NARZĘDZIOWNIA",
    "NARZĘDZIOWNIA HAAS",
    "MALARNIA",
    "GRATOWARKA ERNST",
    "GRADOWARKA BĘBEN",
    "PEDDRAZZOLI",
]

PREFERRED_WORK_CENTERS_BY_OPERATION_TYPE = {
    "laser_sheet_cutting": ["LASER", "WYKRAWARKA E5"],
    "laser_tube_or_profile_cutting": ["LASER DO RUR"],
    "saw_or_profile_cutting": ["LASER DO RUR", "PEDDRAZZOLI"],
    "cnc_bending_sheet": ["GIĘTARKA SAFAN", "GIĘTARKI CNC"],
    "cnc_bending_tube": ["GIĘTARKI CNC"],
    "cnc_bending_wire": ["GIĘTARKI CNC"],
    "wire_straightening_cutting": ["PROŚCIARKI"],
    "mig_manual_welding": ["SPAWALNIA"],
    "robot_welding": ["ROBOT"],
    "spot_welding": ["ZGRZEWARKI", "ZGRZEWARKI AUTOMATYCZNE"],
    "deburring_manual_finishing": ["PRASY", "GRATOWARKA ERNST", "GRADOWARKA BĘBEN"],
    "grinding": ["PRASY", "GRATOWARKA ERNST"],
    "assembly": ["MONTAŻ"],
    "packaging": ["PAKOWANIE"],
    "pressing": ["PRASY", "PRASY MIMOŚRODOWE", "PRASA AUTOMATYCZNA 100t"],
    "milling": ["NARZĘDZIOWNIA HAAS", "NARZĘDZIOWNIA"],
    "drilling": ["NARZĘDZIOWNIA", "NARZĘDZIOWNIA HAAS"],
    "turning": ["NARZĘDZIOWNIA"],
    "painting": ["MALARNIA"],
    "galvanizing": ["PEDDRAZZOLI"],
    "subcontracting": ["PEDDRAZZOLI"],
    "manual_review": [],
    "unknown_operation": [],
}


def get_preferred_work_centers(operation_type: str) -> list[str]:
    """Return ordered preferred work centers for an operation type."""

    return PREFERRED_WORK_CENTERS_BY_OPERATION_TYPE.get(operation_type, [])
