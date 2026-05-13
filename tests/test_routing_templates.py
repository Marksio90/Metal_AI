"""
Tests for routing templates — 5 product families.
"""

import pytest

from metal_calc.data.routing_templates import (
    ROUTING_TEMPLATES,
    get_template,
    WIRE, SHEET, TUBE, MESH, STRUCTURE,
)
from metal_calc.data.machine_rates_2025 import MACHINE_RATES
from metal_calc.models.enums import ProductFamily, OperationType


class TestRegistryCompleteness:
    def test_all_5_families_present(self):
        assert set(ROUTING_TEMPLATES.keys()) == set(ProductFamily)

    def test_get_template_all(self):
        for family in ProductFamily:
            t = get_template(family)
            assert t.family == family


class TestWireTemplate:
    def test_mandatory_step_is_straightening(self):
        mandatory = [s.op_type for s in WIRE.mandatory_steps()]
        assert OperationType.STRAIGHTENING in mandatory

    def test_optional_bending(self):
        optional = [s.op_type for s in WIRE.optional_steps()]
        assert OperationType.WIRE_BENDING in optional

    def test_candidate_machines_exist_in_registry(self):
        for step in WIRE.steps:
            for m in step.candidate_machines:
                assert m in MACHINE_RATES, f"Machine '{m}' in WIRE routing not in registry"


class TestSheetTemplate:
    def test_nesting_is_mandatory(self):
        mandatory = [s.op_type for s in SHEET.mandatory_steps()]
        assert OperationType.NESTING in mandatory

    def test_laser_is_optional(self):
        optional = [s.op_type for s in SHEET.optional_steps()]
        assert OperationType.LASER_CUTTING in optional

    def test_required_fields_include_nesting(self):
        assert "nesting_sheets_count" in SHEET.required_rfq_fields


class TestTubeTemplate:
    def test_cutting_is_mandatory(self):
        mandatory = [s.op_type for s in TUBE.mandatory_steps()]
        assert OperationType.TUBE_CUTTING in mandatory

    def test_laser_rur_in_candidates(self):
        step = TUBE.step_by_op(OperationType.TUBE_CUTTING)
        assert step is not None
        assert "Laser Fiber do rur" in step.candidate_machines


class TestMeshTemplate:
    def test_straightening_and_spotwelds_mandatory(self):
        mandatory = {s.op_type for s in MESH.mandatory_steps()}
        assert OperationType.STRAIGHTENING in mandatory
        assert OperationType.WELDING_SPOT in mandatory


class TestStructureTemplate:
    def test_assembly_is_mandatory(self):
        mandatory = [s.op_type for s in STRUCTURE.mandatory_steps()]
        assert OperationType.ASSEMBLY in mandatory


class TestAllMachineReferences:
    """Every machine referenced in routing templates must exist in MACHINE_RATES."""

    def test_no_dangling_machine_references(self):
        missing = []
        for family, template in ROUTING_TEMPLATES.items():
            for step in template.steps:
                for m in step.candidate_machines:
                    if m not in MACHINE_RATES:
                        missing.append(f"{family.value}/{step.op_type.value}: '{m}'")
        assert missing == [], "Dangling machine references:\n" + "\n".join(missing)
