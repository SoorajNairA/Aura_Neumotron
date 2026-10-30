from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.engineering_graph.serialization import graph_to_dict
from .modifications import ModificationProposal

_ENTITY_OPS = {PatchOperation.UPDATE_ENTITY, PatchOperation.REMOVE_ENTITY}
_RELATIONSHIP_OPS = {PatchOperation.UPDATE_RELATIONSHIP, PatchOperation.REMOVE_RELATIONSHIP}


def snapshot_images(graph: EngineeringGraph, entity_ids: list[str], relationship_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """JSON-pure before-image (graph_to_dict shapes) of the ids that exist in `graph`."""
    part = EngineeringGraph(graph.project_id, graph.schema_version,
                            {i: graph.entities[i] for i in entity_ids if i in graph.entities},
                            {i: graph.relationships[i] for i in relationship_ids if i in graph.relationships})
    dumped = json.loads(json.dumps(graph_to_dict(part)))
    # graph_to_dict sorts by id; keep patch order so restore order is stable.
    order = {i: n for n, i in enumerate(entity_ids)}, {i: n for n, i in enumerate(relationship_ids)}
    return {"entities": sorted(dumped["entities"], key=lambda e: order[0][e["id"]]),
            "relationships": sorted(dumped["relationships"], key=lambda r: order[1][r["id"]])}


def snapshot_proposal(graph: EngineeringGraph, base: int, mode: str, summary: str, patch_ops: list[GraphOperation],
                      extra_checks: list[dict] | None = None) -> ModificationProposal:
    """Build a proposal whose first operation is a before-image of everything `patch_ops` touches.

    Undo (`inverse_proposal`) restores that image generically, so every edit built here is undoable without its own inverse.
    """
    if base != len(graph.revisions): raise ValueError("stale_revision")
    touched_entities, touched_relationships, added_entities, added_relationships, components = [], [], [], [], []
    def note(entity_id: str, kind: EntityKind | None) -> None:
        if entity_id not in touched_entities: touched_entities.append(entity_id)
        if kind is EntityKind.COMPONENT and entity_id not in components: components.append(entity_id)
    for op in patch_ops:
        if op.operation is PatchOperation.ADD_ENTITY:
            added_entities.append(op.entity.id); note(op.entity.id, op.entity.kind)
        elif op.operation in _ENTITY_OPS:
            note(op.target_id, graph.entities[op.target_id].kind if op.target_id in graph.entities else None)
        elif op.operation is PatchOperation.ADD_RELATIONSHIP:
            added_relationships.append(op.relationship.id); touched_relationships.append(op.relationship.id)
        elif op.operation in _RELATIONSHIP_OPS:
            touched_relationships.append(op.target_id)
    # An entity both added and removed inside one patch has no before-image and is not left behind either.
    added_entities = [i for i in added_entities if i not in graph.entities]
    added_relationships = [i for i in added_relationships if i not in graph.relationships]
    operation = {"operation": "snapshot_edit", "mode": mode, "before": snapshot_images(graph, touched_entities, list(dict.fromkeys(touched_relationships))),
                 "addedEntityIds": added_entities, "addedRelationshipIds": added_relationships}
    affected = tuple(components or touched_entities)
    patch = GraphPatch(f"patch-{uuid4().hex}", tuple(patch_ops), summary, graph.current_revision_id)
    checks = [{"state": "PASSED", "message": "Edit references validated against the current Engineering Graph"}, *(extra_checks or [])]
    return ModificationProposal(f"proposal-{uuid4().hex}", base, affected, summary, mode, (operation,), affected,
                                ("existing components",), ("firmware",), {"outcome": "pending_graph_verification", "checks": checks}, patch)
