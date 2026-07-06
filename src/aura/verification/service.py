from __future__ import annotations

from dataclasses import replace

from aura.engineering_graph.model import EngineeringEntity, EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.planner.schemas import ProjectPlan

from .results import VerificationDecision, VerificationFinding, VerificationResult, VerificationState


class VerificationService:
    """Apply deterministic schema, reference, and safety checks to a proposal."""

    def verify(self, plan: ProjectPlan) -> VerificationResult:
        try:
            plan.validate()
        except ValueError as exc:
            return VerificationResult(
                VerificationDecision.REJECT, VerificationState.FAILED, (str(exc),), None
            )
        project_count = sum(entity.kind == EntityKind.PROJECT for entity in plan.entities)
        if project_count != 1:
            return VerificationResult(
                VerificationDecision.REJECT, VerificationState.FAILED,
                ("A project plan must contain exactly one project entity",), None,
            )
        if plan.components:
            return self._verify_engineering_plan(plan)
        forbidden = {"run_shell", "execute_command", "delete_path"}
        if any(operation.operation.value in forbidden for operation in plan.patch.operations):
            return VerificationResult(
                VerificationDecision.REJECT, VerificationState.UNSUPPORTED,
                ("Planner proposal contains an unsupported operation",), None,
            )

        # The planner may only propose conceptual entities. Verification owns
        # status assignment and returns a transformed, independently approved patch.
        operations: list[GraphOperation] = []
        modified = False
        for operation in plan.patch.operations:
            if operation.operation == PatchOperation.ADD_ENTITY and operation.entity is not None:
                entity = operation.entity
                normalized_name = entity.name.strip()
                verified = replace(
                    entity, name=normalized_name,
                    verification_status=VerificationState.TOOL_VERIFIED.value,
                )
                operations.append(replace(operation, entity=verified))
                modified = modified or verified != entity
            else:
                operations.append(operation)
        patch = replace(plan.patch, operations=tuple(operations))
        decision = VerificationDecision.MODIFY if modified else VerificationDecision.ACCEPT
        return VerificationResult(
            decision, VerificationState.TOOL_VERIFIED,
            ("Schema, references, and permitted operation types passed deterministic checks",), patch,
        )

    def _verify_engineering_plan(self, plan: ProjectPlan) -> VerificationResult:
        components = {item.id: item for item in plan.components}
        connections = list(plan.connections)
        findings: list[VerificationFinding] = []

        def add(check: str, state: VerificationState, severity: str, message: str, *ids: str) -> None:
            findings.append(VerificationFinding(
                f"verification-{check}-{len(findings)+1}", check, state, severity, message, tuple(ids)
            ))

        direct = [c for c in connections if {c.source_id, c.target_id} == {"component-esp32", "component-pump"}]
        if direct:
            add("direct-pump-gpio", VerificationState.FAILED, "critical", "Pump must not be driven directly from an ESP32 GPIO.", "component-esp32", "component-pump")
        driver = components.get("component-driver")
        if driver is None:
            add("missing-driver", VerificationState.FAILED, "warning", "A relay, MOSFET, or motor driver is required for the pump.", "component-pump")
        elif driver.parameters.get("driver_type") not in {"relay", "logic-level-mosfet", "motor-driver"}:
            add("invalid-driver", VerificationState.FAILED, "critical", "The declared pump driver type is unsupported.", driver.id)

        power = components.get("component-power")
        pump = components.get("component-pump")
        if power and pump:
            if float(power.parameters.get("voltage_v", 0)) != float(pump.parameters.get("voltage_v", -1)):
                add("voltage", VerificationState.FAILED, "critical", "Pump voltage does not match the selected power source.", power.id, pump.id)
            if float(power.parameters.get("available_current_a", 0)) < float(pump.parameters.get("current_a", 0)):
                add("current", VerificationState.FAILED, "critical", "Power source current is below the pump requirement.", power.id, pump.id)
        types = {c.connection_type for c in connections}
        if "power" not in types and "switched-power" not in types:
            add("power-connection", VerificationState.FAILED, "critical", "Required power connections are missing.", "component-power")
        if "ground" not in types:
            add("ground", VerificationState.FAILED, "critical", "A common logic ground connection is missing.", "component-esp32", "component-power")
        if driver and float(driver.parameters.get("logic_voltage_v", 0)) != 3.3:
            add("logic-level", VerificationState.FAILED, "critical", "Driver logic input is not compatible with ESP32 3.3 V logic.", driver.id, "component-esp32")
        if driver and pump and pump.parameters.get("inductive_load") and not driver.parameters.get("flyback_protection"):
            add("flyback", VerificationState.ESTIMATED, "warning", "Inductive pump load needs verified flyback protection.", driver.id, pump.id)

        for component in components.values():
            for dimension, value in component.dimensions.items():
                if not isinstance(value, dict) or "value" not in value or not value.get("unit"):
                    add("dimension-unit", VerificationState.FAILED, "critical", f"{component.name} {dimension} lacks an explicit unit.", component.id)
            if not component.dimensions:
                add("dimensions", VerificationState.CONCEPTUAL, "warning", f"Exact dimensions are missing for {component.name}.", component.id)
        fluid_pairs = [{c.source_id, c.target_id} for c in connections if c.connection_type == "fluid"]
        if {"component-reservoir", "component-tubing"} not in fluid_pairs or {"component-tubing", "component-pump"} not in fluid_pairs:
            add("water-path", VerificationState.FAILED, "critical", "Tubing must connect the reservoir to the pump inlet.", "component-reservoir", "component-tubing", "component-pump")
        enclosure = components.get("component-enclosure")
        if not enclosure or not enclosure.parameters.get("waterproofing"):
            add("water-separation", VerificationState.FAILED, "warning", "Water and exposed electronics need an enclosure or waterproofing assumption.", "component-esp32")
        elif enclosure.dimensions:
            enclosure_width = enclosure.dimensions.get("width", {}).get("value", 0)
            enclosure_length = enclosure.dimensions.get("length", {}).get("value", 0)
            for contained_id in enclosure.parameters.get("contains", []):
                contained = components.get(contained_id)
                if contained and (contained.dimensions.get("width", {}).get("value", 0) > enclosure_width or contained.dimensions.get("length", {}).get("value", 0) > enclosure_length):
                    add("enclosure-fit", VerificationState.FAILED, "critical", f"{contained.name} does not fit the declared enclosure dimensions.", enclosure.id, contained.id)
        if power and power.parameters.get("mains_exposed"):
            add("mains", VerificationState.FAILED, "critical", "Exposed mains power is not permitted; use an isolated low-voltage DC supply.", power.id)

        critical = [finding for finding in findings if finding.severity == "critical"]
        if critical:
            return VerificationResult(VerificationDecision.REJECT, VerificationState.FAILED, tuple(f.message for f in critical), None, tuple(findings))

        operations = []
        for operation in plan.patch.operations:
            if operation.operation == PatchOperation.ADD_ENTITY and operation.entity:
                status = VerificationState.CROSS_CHECKED.value
                operations.append(replace(operation, entity=replace(operation.entity, verification_status=status)))
            else:
                operations.append(operation)
        project_id = next(entity.id for entity in plan.entities if entity.kind == EntityKind.PROJECT)
        for finding in findings:
            operations.append(GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(
                finding.id, EntityKind.VERIFICATION_RESULT, finding.message, project_id,
                {"check": finding.check, "severity": finding.severity, "entity_ids": list(finding.entity_ids)},
                verification_status=finding.state.value,
            )))
        patch = replace(plan.patch, operations=tuple(operations))
        return VerificationResult(VerificationDecision.MODIFY, VerificationState.CROSS_CHECKED,
            ("Structural, electrical, physical, and safety rules completed.",), patch, tuple(findings))

    def verify_modification(self, graph, patch: GraphPatch) -> VerificationResult:
        affected = {operation.target_id for operation in patch.operations if operation.target_id}
        operations = list(patch.operations)
        for result in graph.find(kind=EntityKind.VERIFICATION_RESULT):
            result_entities = set(result.metadata.get("entity_ids", []))
            if result_entities & affected:
                operations.append(GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=result.id, changes={"verification_status": VerificationState.STALE.value}))
        operations.append(GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(
            "verification-mosfet-update", EntityKind.VERIFICATION_RESULT,
            "MOSFET driver logic level and flyback protection require implementation confirmation.", graph.project_id,
            {"check": "driver-update", "severity": "warning", "entity_ids": ["component-driver"]},
            verification_status=VerificationState.ESTIMATED.value,
        )))
        return VerificationResult(VerificationDecision.MODIFY, VerificationState.ESTIMATED,
            ("Only driver-dependent checks were rerun.",), replace(patch, operations=tuple(operations)),
            (VerificationFinding("verification-mosfet-update", "driver-update", VerificationState.ESTIMATED, "warning", "MOSFET selection requires implementation confirmation.", ("component-driver",)),))
