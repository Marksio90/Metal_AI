"""
Technology library: product families → allowed operations → candidate machines.

Each RoutingStep defines one operation slot in a routing:
  - op_type         : the OperationType enum value
  - mandatory       : True = must be filled before calc, False = optional
  - candidate_machines: ordered list of machine names from MACHINE_RATES
  - required_inputs : field names that must be present to price this step
  - unit            : time unit ('s' = seconds — the only unit used here)

A ProductFamilyTemplate groups all steps for one family, in execution order.
Operators pick which optional steps apply; mandatory steps are always costed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence

from metal_calc.models.enums import OperationType, ProductFamily


@dataclass(frozen=True)
class RoutingStep:
    op_type: OperationType
    mandatory: bool
    candidate_machines: tuple[str, ...]
    required_inputs: tuple[str, ...]
    unit: str = "s"
    notes: str = ""


@dataclass(frozen=True)
class ProductFamilyTemplate:
    family: ProductFamily
    label_pl: str
    required_rfq_fields: tuple[str, ...]
    steps: tuple[RoutingStep, ...]

    def mandatory_steps(self) -> list[RoutingStep]:
        return [s for s in self.steps if s.mandatory]

    def optional_steps(self) -> list[RoutingStep]:
        return [s for s in self.steps if not s.mandatory]

    def step_by_op(self, op: OperationType) -> RoutingStep | None:
        for s in self.steps:
            if s.op_type == op:
                return s
        return None


# ---------------------------------------------------------------------------
# Wire family
# ---------------------------------------------------------------------------
WIRE = ProductFamilyTemplate(
    family=ProductFamily.WIRE,
    label_pl="Drut",
    required_rfq_fields=(
        "material_family",
        "material_grade",
        "wire_diameter_mm",
        "quantity",
        "unit_mass_kg",
        "finish",
    ),
    steps=(
        RoutingStep(
            op_type=OperationType.STRAIGHTENING,
            mandatory=True,
            candidate_machines=("Prościarki do drutu", "Fazowarka Varo"),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WIRE_BENDING,
            mandatory=False,
            candidate_machines=("Giętarka Montorfano", "Giętarka rur CNC Veenstra"),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_SPOT,
            mandatory=False,
            candidate_machines=(
                "Zgrzewarka Ideal", "Zgrzewarka 3D", "Zgrzewarka CEMSA",
                "Zgrzewarka Varo", "Zgrzewarka 5D kleszczowa do ramek",
                "Zgrzewarka Kempi", "Zgrzewarka Dabew", "Zgrzewarka Clifford",
                "Zgrzewarka doczołowa CEA", "Zgrzewarki ręczne",
                "Obcinarka Varo", "Zgrzewarka Varo 2 2022 roku",
                "Zgrzewarka Schlatter",
            ),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_MANUAL,
            mandatory=False,
            candidate_machines=("Spawanie ręczne",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.POWDER_COATING,
            mandatory=False,
            candidate_machines=("Malarnia proszkowa",),
            required_inputs=("setup_sec", "cycle_sec", "quantity", "surface_dm2"),
            notes="Surface in dm² required for powder coating capacity check",
        ),
        RoutingStep(
            op_type=OperationType.FLUID_COATING,
            mandatory=False,
            candidate_machines=("Malarnia fluidyzacyjna",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.GALVANIZING,
            mandatory=False,
            candidate_machines=("Cynkownia",),
            required_inputs=("unit_mass_kg", "quantity"),
            notes="Outside service — priced per kg or dm², not by machine-seconds",
        ),
        RoutingStep(
            op_type=OperationType.ASSEMBLY,
            mandatory=False,
            candidate_machines=("Montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.PACKAGING,
            mandatory=False,
            candidate_machines=("Pakowanie/montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.PACKAGING_AUTO,
            mandatory=False,
            candidate_machines=("Pakowanie automatyczne",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Sheet metal family
# ---------------------------------------------------------------------------
SHEET = ProductFamilyTemplate(
    family=ProductFamily.SHEET,
    label_pl="Blacha",
    required_rfq_fields=(
        "material_family",
        "material_grade",
        "thickness_mm",
        "quantity",
        "unit_mass_kg",
        "finish",
        "nesting_sheets_count",
    ),
    steps=(
        RoutingStep(
            op_type=OperationType.NESTING,
            mandatory=True,
            candidate_machines=(),
            required_inputs=("nesting_sheets_count", "sheet_format"),
            notes="Nesting result (number of sheets, cutting time) must be imported "
                  "before laser/punching times can be confirmed",
        ),
        RoutingStep(
            op_type=OperationType.LASER_CUTTING,
            mandatory=False,
            candidate_machines=("Laser Fiber do blach",),
            required_inputs=("setup_sec", "cycle_sec", "nesting_sheets_count"),
        ),
        RoutingStep(
            op_type=OperationType.PUNCHING,
            mandatory=False,
            candidate_machines=("Wykrawarka Prima Power E5",),
            required_inputs=("setup_sec", "cycle_sec", "nesting_sheets_count"),
        ),
        RoutingStep(
            op_type=OperationType.DEBURRING,
            mandatory=False,
            candidate_machines=("Gratowarka do blach ERNST",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.SHEET_BENDING,
            mandatory=False,
            candidate_machines=("Giętarka do blach SAFAN",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_ROBOT,
            mandatory=False,
            candidate_machines=("Robot spawalniczy Fanuc",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_MANUAL,
            mandatory=False,
            candidate_machines=("Spawanie ręczne",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.POWDER_COATING,
            mandatory=False,
            candidate_machines=("Malarnia proszkowa",),
            required_inputs=("setup_sec", "cycle_sec", "quantity", "surface_dm2"),
        ),
        RoutingStep(
            op_type=OperationType.FLUID_COATING,
            mandatory=False,
            candidate_machines=("Malarnia fluidyzacyjna",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.GALVANIZING,
            mandatory=False,
            candidate_machines=("Cynkownia",),
            required_inputs=("unit_mass_kg", "quantity"),
            notes="Outside service",
        ),
        RoutingStep(
            op_type=OperationType.ASSEMBLY,
            mandatory=False,
            candidate_machines=("Montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.PACKAGING,
            mandatory=False,
            candidate_machines=("Pakowanie/montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Tube / profile family
# ---------------------------------------------------------------------------
TUBE = ProductFamilyTemplate(
    family=ProductFamily.TUBE,
    label_pl="Rura / Profil",
    required_rfq_fields=(
        "material_family",
        "material_grade",
        "tube_od_mm",
        "wall_thickness_mm",
        "length_mm",
        "quantity",
        "unit_mass_kg",
        "finish",
    ),
    steps=(
        RoutingStep(
            op_type=OperationType.TUBE_CUTTING,
            mandatory=True,
            candidate_machines=(
                "Laser Fiber do rur",
                "Automat do cięcia rur Pedrazzoli",
                "Piła taśmowa do rur",
            ),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.TUBE_BENDING,
            mandatory=False,
            candidate_machines=(
                "Giętarka rur CNC BLM Elect",
                "Giętarka rur CNC Veenstra",
                "Giętarka do rur SOCO",
            ),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.DRILLING,
            mandatory=False,
            candidate_machines=("Wiertarka kolumnowa",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.DEBURRING,
            mandatory=False,
            candidate_machines=("Gratowarka do rur RSA", "Gratowarka wibracyjna Rosler"),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_ROBOT,
            mandatory=False,
            candidate_machines=("Robot spawalniczy Fanuc",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_MANUAL,
            mandatory=False,
            candidate_machines=("Spawanie ręczne",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.POWDER_COATING,
            mandatory=False,
            candidate_machines=("Malarnia proszkowa",),
            required_inputs=("setup_sec", "cycle_sec", "quantity", "surface_dm2"),
        ),
        RoutingStep(
            op_type=OperationType.GALVANIZING,
            mandatory=False,
            candidate_machines=("Cynkownia",),
            required_inputs=("unit_mass_kg", "quantity"),
            notes="Outside service",
        ),
        RoutingStep(
            op_type=OperationType.ASSEMBLY,
            mandatory=False,
            candidate_machines=("Montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.PACKAGING,
            mandatory=False,
            candidate_machines=("Pakowanie/montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Mesh / frame family
# ---------------------------------------------------------------------------
MESH = ProductFamilyTemplate(
    family=ProductFamily.MESH,
    label_pl="Siatka / Rama",
    required_rfq_fields=(
        "material_family",
        "material_grade",
        "wire_diameter_mm",
        "mesh_width_mm",
        "mesh_height_mm",
        "quantity",
        "unit_mass_kg",
        "finish",
    ),
    steps=(
        RoutingStep(
            op_type=OperationType.STRAIGHTENING,
            mandatory=True,
            candidate_machines=("Prościarki do drutu",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WELDING_SPOT,
            mandatory=True,
            candidate_machines=(
                "Zgrzewarka Ideal", "Zgrzewarka 3D", "Zgrzewarka CEMSA",
                "Zgrzewarka Varo", "Zgrzewarka 5D kleszczowa do ramek",
                "Zgrzewarka Schlatter",
            ),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.WIRE_BENDING,
            mandatory=False,
            candidate_machines=("Giętarka Montorfano",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.POWDER_COATING,
            mandatory=False,
            candidate_machines=("Malarnia proszkowa",),
            required_inputs=("setup_sec", "cycle_sec", "quantity", "surface_dm2"),
        ),
        RoutingStep(
            op_type=OperationType.GALVANIZING,
            mandatory=False,
            candidate_machines=("Cynkownia",),
            required_inputs=("unit_mass_kg", "quantity"),
            notes="Outside service",
        ),
        RoutingStep(
            op_type=OperationType.PACKAGING,
            mandatory=False,
            candidate_machines=("Pakowanie/montaż", "Pakowanie automatyczne"),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Structure / rack family (multi-level BOM)
# ---------------------------------------------------------------------------
STRUCTURE = ProductFamilyTemplate(
    family=ProductFamily.STRUCTURE,
    label_pl="Konstrukcja / Regał",
    required_rfq_fields=(
        "component_list",
        "quantity",
        "finish",
        "assembly_description",
    ),
    steps=(
        RoutingStep(
            op_type=OperationType.WELDING_ROBOT,
            mandatory=False,
            candidate_machines=("Robot spawalniczy Fanuc",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
            notes="For repeatable sub-assemblies only",
        ),
        RoutingStep(
            op_type=OperationType.WELDING_MANUAL,
            mandatory=False,
            candidate_machines=("Spawanie ręczne",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.POWDER_COATING,
            mandatory=False,
            candidate_machines=("Malarnia proszkowa",),
            required_inputs=("setup_sec", "cycle_sec", "quantity", "surface_dm2"),
        ),
        RoutingStep(
            op_type=OperationType.FLUID_COATING,
            mandatory=False,
            candidate_machines=("Malarnia fluidyzacyjna",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.GALVANIZING,
            mandatory=False,
            candidate_machines=("Cynkownia",),
            required_inputs=("unit_mass_kg", "quantity"),
            notes="Outside service",
        ),
        RoutingStep(
            op_type=OperationType.ASSEMBLY,
            mandatory=True,
            candidate_machines=("Montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
        RoutingStep(
            op_type=OperationType.PACKAGING,
            mandatory=False,
            candidate_machines=("Pakowanie/montaż",),
            required_inputs=("setup_sec", "cycle_sec", "quantity"),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
ROUTING_TEMPLATES: dict[ProductFamily, ProductFamilyTemplate] = {
    ProductFamily.WIRE: WIRE,
    ProductFamily.SHEET: SHEET,
    ProductFamily.TUBE: TUBE,
    ProductFamily.MESH: MESH,
    ProductFamily.STRUCTURE: STRUCTURE,
}


def get_template(family: ProductFamily) -> ProductFamilyTemplate:
    return ROUTING_TEMPLATES[family]
