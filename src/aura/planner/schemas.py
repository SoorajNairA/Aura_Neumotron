from __future__ import annotations

from dataclasses import dataclass

from aura.engineering_graph.model import EntityKind
from aura.engineering_graph.patches import GraphPatch


@dataclass(frozen=True)
class ProjectRequest:
    project_name: str
    objective: str
    requirements: tuple[str, ...]
    components: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    representation: str = "system_diagram"

    def validate(self) -> None:
        if not self.project_name.strip() or not self.objective.strip():
            raise ValueError("Project name and objective are required")
        if not self.requirements:
            raise ValueError("At least one requirement is required")
        if any(not value.strip() for value in (*self.requirements, *self.components, *self.assumptions)):
            raise ValueError("Request values must not be blank")


@dataclass(frozen=True)
class PlannedEntity:
    id: str
    kind: EntityKind
    name: str
    parent_id: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PlannedRelationship:
    id: str
    source_id: str
    target_id: str
    type: str


@dataclass(frozen=True)
class RepresentationRequest:
    entity_id: str
    representation_type: str


@dataclass(frozen=True)
class VerificationRequest:
    patch_id: str
    checks: tuple[str, ...]


@dataclass(frozen=True)
class WorkspaceEventProposal:
    event_type: str
    entity_id: str


@dataclass(frozen=True)
class ProjectPlan:
    request: ProjectRequest
    entities: tuple[PlannedEntity, ...]
    relationships: tuple[PlannedRelationship, ...]
    patch: GraphPatch
    representation_requests: tuple[RepresentationRequest, ...]
    verification_request: VerificationRequest
    workspace_events: tuple[WorkspaceEventProposal, ...]

    def validate(self) -> None:
        self.request.validate()
        ids = [entity.id for entity in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("Planner output contains duplicate entity ids")
        known = set(ids)
        for entity in self.entities:
            if entity.parent_id is not None and entity.parent_id not in known:
                raise ValueError(f"Planner output references missing parent {entity.parent_id}")
        for relationship in self.relationships:
            if relationship.source_id not in known or relationship.target_id not in known:
                raise ValueError(f"Planner relationship {relationship.id} has a missing endpoint")
        if self.verification_request.patch_id != self.patch.id:
            raise ValueError("Verification request must reference the proposed patch")
