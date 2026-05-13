from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class OperationType(StrEnum):
    LASER_CUTTING = "laser_cutting"
    BENDING = "bending"
    WELDING = "welding"
    DEBURRING = "deburring"
    PAINTING = "painting"
    GALVANIZING = "galvanizing"
    ASSEMBLY = "assembly"
    SUBCONTRACTING = "subcontracting"
    MANUAL_REVIEW = "manual_review"


@dataclass(slots=True)
class CustomerInfo:
    name: str
    country: str = "unknown"


@dataclass(slots=True)
class MaterialSpec:
    material_code: str  # S235, S355, stainless_steel, aluminum, unknown_material
    thickness_mm: float | None = None


@dataclass(slots=True)
class FinishSpec:
    finish_code: str = "unknown_finish"


@dataclass(slots=True)
class PartSpec:
    part_name: str
    geometry_ref: str | None = None
    mass_kg: float | None = None


@dataclass(slots=True)
class QuantityBreak:
    quantity: int


@dataclass(slots=True)
class ManufacturingOperation:
    operation: OperationType
    assumptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskFlag:
    code: str
    severity: str
    message: str


@dataclass(slots=True)
class ConfidenceScore:
    value: float
    rationale: str


@dataclass(slots=True)
class ManufacturingRoute:
    operations: list[ManufacturingOperation]
    confidence: ConfidenceScore
    risks: list[RiskFlag]
    assumptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MachineRate:
    operation: OperationType
    hourly_rate: float


@dataclass(slots=True)
class CostBreakdown:
    material_cost: float
    operation_cost: float
    finishing_cost: float
    subcontracting_cost: float
    total_cost: float
    assumptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MissingInformation:
    fields: list[str]


@dataclass(slots=True)
class QuoteResult:
    route: ManufacturingRoute
    costs: CostBreakdown
    missing_information: MissingInformation
    assumptions: list[str]


@dataclass(slots=True)
class RFQInput:
    customer: CustomerInfo
    part: PartSpec
    material: MaterialSpec
    finish: FinishSpec
    quantity_break: QuantityBreak
    requested_operations: list[OperationType] = field(default_factory=list)
