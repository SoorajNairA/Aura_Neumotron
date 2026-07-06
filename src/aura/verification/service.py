from __future__ import annotations

from dataclasses import replace

from aura.engineering_graph.model import EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.planner.schemas import ProjectPlan

from .results import VerificationDecision, VerificationResult, VerificationState


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
