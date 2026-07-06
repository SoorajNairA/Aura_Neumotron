from __future__ import annotations

import re
from uuid import NAMESPACE_URL, uuid5

from aura.engineering_graph.model import EngineeringEntity, EntityKind, Relationship
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation

from .schemas import (
    PlannedEntity, PlannedRelationship, ProjectPlan, ProjectRequest,
    RepresentationRequest, VerificationRequest, WorkspaceEventProposal,
)


class PlannerService:
    """Produce a deterministic, structured proposal without executing it."""

    def plan(self, request: ProjectRequest) -> ProjectPlan:
        request.validate()
        project_id = self._id(request.project_name, "project")
        assembly_id = self._id(request.project_name, "assembly")
        planned = [
            PlannedEntity(project_id, EntityKind.PROJECT, request.project_name.strip()),
            PlannedEntity(assembly_id, EntityKind.ASSEMBLY, "Primary Assembly", project_id),
        ]
        for index, requirement in enumerate(request.requirements, 1):
            planned.append(PlannedEntity(
                self._id(request.project_name, f"requirement-{index}"), EntityKind.REQUIREMENT,
                requirement.strip(), project_id,
            ))
        for index, assumption in enumerate(request.assumptions, 1):
            planned.append(PlannedEntity(
                self._id(request.project_name, f"assumption-{index}"), EntityKind.ASSUMPTION,
                assumption.strip(), project_id,
            ))
        for index, component in enumerate(request.components, 1):
            planned.append(PlannedEntity(
                self._id(request.project_name, f"component-{index}"), EntityKind.COMPONENT,
                component.strip(), assembly_id,
            ))
        representation_id = self._id(request.project_name, "representation")
        planned.append(PlannedEntity(
            representation_id, EntityKind.REPRESENTATION, request.representation,
            project_id, (("representation_type", request.representation),),
        ))

        relationships = tuple(
            PlannedRelationship(
                self._id(request.project_name, f"contains-{index}"), assembly_id, entity.id, "contains"
            )
            for index, entity in enumerate(planned)
            if entity.kind == EntityKind.COMPONENT
        )
        operations = [
            GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(
                id=item.id, kind=item.kind, name=item.name, parent_id=item.parent_id,
                metadata=dict(item.metadata),
            ))
            for item in planned
        ]
        operations.extend(
            GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=Relationship(
                id=item.id, source_id=item.source_id, target_id=item.target_id, type=item.type,
            ))
            for item in relationships
        )
        patch = GraphPatch(
            id=self._id(request.project_name, "initial-patch"), operations=tuple(operations),
            summary=f"Create engineering graph for {request.project_name.strip()}",
        )
        plan = ProjectPlan(
            request=request, entities=tuple(planned), relationships=relationships, patch=patch,
            representation_requests=(RepresentationRequest(project_id, request.representation),),
            verification_request=VerificationRequest(patch.id, ("schema", "references", "safety")),
            workspace_events=(WorkspaceEventProposal("project.created", project_id),),
        )
        plan.validate()
        return plan

    @staticmethod
    def _id(project_name: str, role: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        return f"{role}-{uuid5(NAMESPACE_URL, f'aura:{normalized}:{role}').hex}"
