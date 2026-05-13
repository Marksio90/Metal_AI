"""
CalcForm — interactive builder that maps routing-template steps + filled seconds
into a QuoteItem ready for the calculation engine.

Usage:
    form = CalcForm.from_template(WIRE, item_name="Drut fi5 S235", quantity=500)
    form.fill_operation(OperationType.STRAIGHTENING, "Prościarki do drutu",
                        setup_sec=180, cycle_sec=3.5)
    form.fill_material("Drut S235JR fi5", unit="kg", quantity_net=125.0,
                       scrap_factor=1.02, price_per_unit=4.20,
                       price_source="cennik_miesięczny")
    errors = form.validate()   # [] if ready
    item = form.build_quote_item()

For SHEET family (nesting step has no candidate machines):
    form = CalcForm.from_template(SHEET, item_name="Blacha DC01 2mm", quantity=100)
    form.fill_nesting_result(NestingResult(
        n_sheets=10,
        sheet_format="2000x1000",
        cutting_time_per_sheet_s=280.0,
        machine_time_per_sheet_s=320.0,
        material_utilization_pct=82.5,
        setup_per_batch_s=300.0,
    ))
    times = form.suggested_laser_times()
    form.fill_operation(OperationType.LASER_CUTTING, "Laser Fiber do blach",
                        setup_sec=times["setup_sec"], cycle_sec=times["cycle_sec"])
"""

from __future__ import annotations

from dataclasses import dataclass, field

from metal_calc.data.routing_templates import ProductFamilyTemplate, RoutingStep
from metal_calc.engine.calculation import (
    AssumptionEntry,
    MaterialLine,
    OperationLine,
    OutsideServiceLine,
    QuoteItem,
)
from metal_calc.models.enums import OperationType


# ---------------------------------------------------------------------------
# Nesting result (SHEET family input)
# ---------------------------------------------------------------------------

@dataclass
class NestingResult:
    """
    Output from nesting software for one batch of sheet-metal parts.

    n_sheets                  number of physical sheets consumed for the whole batch
    sheet_format              e.g. "2000x1000" (mm)
    cutting_time_per_sheet_s  net laser-on / punch-stroke time per sheet [s]
    machine_time_per_sheet_s  total machine time per sheet including idle [s]
    material_utilization_pct  area of parts / total sheet area × 100  [%]
    setup_per_batch_s         one-off job setup + first-sheet loading time [s]
    nesting_program           reference ID / file name of the nesting job
    note                      free-text remark
    """
    n_sheets: int
    sheet_format: str
    cutting_time_per_sheet_s: float
    machine_time_per_sheet_s: float
    material_utilization_pct: float
    setup_per_batch_s: float = 0.0
    nesting_program: str = ""
    note: str = ""

    def total_machine_time_s(self) -> float:
        """Total machine time for the full batch: setup + n_sheets × per-sheet time."""
        return self.setup_per_batch_s + self.machine_time_per_sheet_s * self.n_sheets

    def suggested_laser_setup_sec(self) -> float:
        """One-off batch setup for the OperationLine (loading + job start)."""
        return self.setup_per_batch_s

    def suggested_laser_cycle_sec(self, qty: int) -> float:
        """
        Per-piece amortized machine time for use in OperationLine.cycle_sec.

        Formula: (n_sheets × machine_time_per_sheet_s) / qty
        With quantity=qty the engine computes:
            eff = setup_sec + cycle_sec * qty = setup_per_batch_s + n_sheets * machine_time_per_sheet_s
        which equals the real total machine time.
        """
        if qty <= 0:
            return 0.0
        return (self.machine_time_per_sheet_s * self.n_sheets) / qty


# ---------------------------------------------------------------------------
# Input containers
# ---------------------------------------------------------------------------

@dataclass
class FilledOperation:
    op_type: OperationType
    machine_name: str
    setup_sec: float
    cycle_sec: float
    extra_sec: float = 0.0
    note: str = ""


@dataclass
class FilledMaterial:
    material_name: str
    unit: str
    quantity_net: float
    scrap_factor: float = 1.0
    price_per_unit: float = 0.0
    price_source: str = ""
    note: str = ""


@dataclass
class FilledOutsideService:
    service_name: str
    service_type: str
    unit: str
    quantity: float
    price_per_unit: float
    price_source: str = ""
    note: str = ""


# ---------------------------------------------------------------------------
# CalcForm
# ---------------------------------------------------------------------------

class CalcForm:
    """
    Form that collects operation seconds, material prices, and outside-service
    costs for one QuoteItem, then validates and builds it.
    """

    def __init__(
        self,
        template: ProductFamilyTemplate,
        item_name: str,
        quantity: int,
    ) -> None:
        self.template = template
        self.item_name = item_name
        self.quantity = quantity
        self._operations: dict[OperationType, FilledOperation] = {}
        self._materials: list[FilledMaterial] = []
        self._outside_services: list[FilledOutsideService] = []
        self._assumptions: list[AssumptionEntry] = []
        self._nesting_result: NestingResult | None = None
        self.packaging_cost_zl: float = 0.0
        self.adjustment_zl: float = 0.0

    @classmethod
    def from_template(
        cls,
        template: ProductFamilyTemplate,
        item_name: str,
        quantity: int,
    ) -> "CalcForm":
        return cls(template, item_name, quantity)

    # ------------------------------------------------------------------
    # Fill methods
    # ------------------------------------------------------------------

    def fill_operation(
        self,
        op_type: OperationType,
        machine_name: str,
        setup_sec: float,
        cycle_sec: float,
        extra_sec: float = 0.0,
        note: str = "",
    ) -> None:
        """Register seconds for one routing-step operation."""
        step = self.template.step_by_op(op_type)
        if step is None:
            raise ValueError(
                f"Operation {op_type.value!r} is not defined in template "
                f"for family {self.template.family.value!r}."
            )
        if machine_name not in step.candidate_machines:
            raise ValueError(
                f"Machine {machine_name!r} is not a candidate for {op_type.value!r}. "
                f"Valid: {list(step.candidate_machines)}"
            )
        self._operations[op_type] = FilledOperation(
            op_type=op_type,
            machine_name=machine_name,
            setup_sec=setup_sec,
            cycle_sec=cycle_sec,
            extra_sec=extra_sec,
            note=note,
        )

    def fill_material(
        self,
        material_name: str,
        unit: str,
        quantity_net: float,
        scrap_factor: float = 1.0,
        price_per_unit: float = 0.0,
        price_source: str = "",
        note: str = "",
    ) -> None:
        self._materials.append(FilledMaterial(
            material_name=material_name,
            unit=unit,
            quantity_net=quantity_net,
            scrap_factor=scrap_factor,
            price_per_unit=price_per_unit,
            price_source=price_source,
            note=note,
        ))

    def fill_nesting_result(self, result: NestingResult) -> None:
        """
        Register a nesting result for SHEET-family quotes.

        Satisfies the mandatory NESTING routing step (which has no candidate
        machines) and makes suggested_laser_times() available.
        """
        self._nesting_result = result

    def suggested_laser_times(self) -> dict | None:
        """
        Return suggested setup_sec / cycle_sec for the LASER_CUTTING operation
        derived from the registered NestingResult, or None if no nesting result.

        Use the returned values in fill_operation(OperationType.LASER_CUTTING, ...):
            times = form.suggested_laser_times()
            form.fill_operation(OperationType.LASER_CUTTING, "Laser Fiber do blach",
                                setup_sec=times["setup_sec"],
                                cycle_sec=times["cycle_sec"])
        """
        r = self._nesting_result
        if r is None:
            return None
        return {
            "setup_sec": r.suggested_laser_setup_sec(),
            "cycle_sec": r.suggested_laser_cycle_sec(self.quantity),
            "n_sheets": r.n_sheets,
            "sheet_format": r.sheet_format,
            "material_utilization_pct": r.material_utilization_pct,
            "total_machine_time_s": r.total_machine_time_s(),
            "nesting_program": r.nesting_program,
        }

    def fill_outside_service(
        self,
        service_name: str,
        service_type: str,
        unit: str,
        quantity: float,
        price_per_unit: float,
        price_source: str = "",
        note: str = "",
    ) -> None:
        self._outside_services.append(FilledOutsideService(
            service_name=service_name,
            service_type=service_type,
            unit=unit,
            quantity=quantity,
            price_per_unit=price_per_unit,
            price_source=price_source,
            note=note,
        ))

    def add_assumption(
        self,
        field_name: str,
        assumed_value: str,
        reason: str,
        confirmed: bool = False,
    ) -> None:
        self._assumptions.append(AssumptionEntry(
            field_name=field_name,
            assumed_value=assumed_value,
            reason=reason,
            confirmed=confirmed,
        ))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty list means ready to build."""
        errors: list[str] = []
        if self.quantity <= 0:
            errors.append("Quantity must be a positive integer.")
        for step in self.template.mandatory_steps():
            if not step.candidate_machines:
                # Step has no machines (e.g. NESTING) — satisfied by a NestingResult.
                if self._nesting_result is None:
                    errors.append(
                        f"Mandatory step {step.op_type.value!r} requires a NestingResult "
                        "(call fill_nesting_result() before validate())."
                    )
            elif step.op_type not in self._operations:
                errors.append(
                    f"Mandatory operation not filled: {step.op_type.value!r} "
                    f"(candidates: {list(step.candidate_machines)})"
                )
        if not self._materials:
            errors.append("No materials defined.")
        return errors

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_quote_item(self) -> QuoteItem:
        """Build a QuoteItem from all filled data. Call validate() first."""
        ops = [
            OperationLine(
                operation_name=f.op_type.value,
                machine_name=f.machine_name,
                setup_sec=f.setup_sec,
                cycle_sec=f.cycle_sec,
                quantity=self.quantity,
                extra_sec=f.extra_sec,
                note=f.note,
            )
            for f in self._operations.values()
        ]
        mats = [
            MaterialLine(
                material_name=m.material_name,
                unit=m.unit,
                quantity_net=m.quantity_net,
                scrap_factor=m.scrap_factor,
                price_per_unit=m.price_per_unit,
                price_source=m.price_source,
                note=m.note,
            )
            for m in self._materials
        ]
        svcs = [
            OutsideServiceLine(
                service_name=s.service_name,
                service_type=s.service_type,
                unit=s.unit,
                quantity=s.quantity,
                price_per_unit=s.price_per_unit,
                price_source=s.price_source,
                note=s.note,
            )
            for s in self._outside_services
        ]
        return QuoteItem(
            item_name=self.item_name,
            product_family=self.template.family.value,
            quantity=self.quantity,
            operations=ops,
            materials=mats,
            outside_services=svcs,
            assumptions=list(self._assumptions),
            packaging_cost_zl=self.packaging_cost_zl,
            adjustment_zl=self.adjustment_zl,
        )

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def unfilled_mandatory_steps(self) -> list[RoutingStep]:
        return [
            s for s in self.template.mandatory_steps()
            if s.op_type not in self._operations
        ]

    def filled_op_types(self) -> list[OperationType]:
        return list(self._operations)

    def operation_summary(self) -> list[dict]:
        """
        Return a list of dicts describing every routing step with fill status
        and computed effective_time_s where available.
        """
        rows = []
        for step in self.template.steps:
            filled = self._operations.get(step.op_type)
            if filled is None:
                rows.append({
                    "op_type": step.op_type.value,
                    "mandatory": step.mandatory,
                    "status": "unfilled",
                    "machine_name": None,
                    "setup_sec": None,
                    "cycle_sec": None,
                    "extra_sec": None,
                    "effective_time_s": None,
                })
            else:
                eff = filled.setup_sec + filled.cycle_sec * self.quantity + filled.extra_sec
                rows.append({
                    "op_type": step.op_type.value,
                    "mandatory": step.mandatory,
                    "status": "filled",
                    "machine_name": filled.machine_name,
                    "setup_sec": filled.setup_sec,
                    "cycle_sec": filled.cycle_sec,
                    "extra_sec": filled.extra_sec,
                    "effective_time_s": round(eff, 3),
                })
        return rows
