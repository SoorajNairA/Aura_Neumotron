from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Literal
from uuid import uuid4

from aura.engineering_graph.electrical import ELECTRICAL_TYPES
from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.engineering_graph.serialization import graph_to_dict
from aura.verification.pins import PinDefinition, pins_for_definition
from .autowire import PART_DRIVES, Wire
from .modifications import ModificationError, ModificationProposal

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


def _pins(entity: EngineeringEntity) -> dict[str, PinDefinition]:
    """The part's pins by name: its own snapshot when it has one, else the catalogue template for its definition/family."""
    if entity.metadata.get("pins"):
        return {p["name"]: PinDefinition(p["name"], p.get("label", p["name"]), p.get("role", "passive"), tuple(p["voltageRange"]) if p.get("voltageRange") else None) for p in entity.metadata["pins"]}
    definition = entity.metadata.get("parameters", {}).get("component_definition_id") or entity.metadata.get("component_definition_id")
    return {p.name: p for p in pins_for_definition(definition, str(entity.metadata.get("family", "")))}


_End = tuple[EngineeringEntity, PinDefinition]


def _end(graph: EngineeringGraph, end: tuple[str, str] | None) -> _End:
    if end is None: raise ModificationError("UNKNOWN_PIN", "Choose a part and a pin for that end of the wire.", 422)
    part_id, pin = end
    part = graph.entities.get(part_id)
    if part is None or part.kind is not EntityKind.COMPONENT: raise ModificationError("UNKNOWN_PIN", "That part is not in the current design.", 404)
    pins = _pins(part)
    if pin not in pins: raise ModificationError("UNKNOWN_PIN", f"{part.name} has no pin {pin}.", 422)
    return part, pins[pin]


def _is_board(end: _End) -> bool:
    return end[0].metadata.get("family") == "microcontroller_board"


def _wire_type(source: _End, target: _End) -> str:
    """power_out to power_in is power; ground to ground is ground; a wire the board drives is control; anything else is signal."""
    roles = {source[1].role, target[1].role}
    if roles == {"power_out", "power_in"}: return "power"
    if roles == {"ground"}: return "ground"
    if _is_board(source) != _is_board(target):
        return "signal" if (target if _is_board(source) else source)[1].role in PART_DRIVES else "control"
    return "signal"


def _canonical(source: _End, target: _End) -> tuple[_End, _End, str]:
    """Order the ends the way auto-wire stores them: supply from the power_out pin, ground and control from the board, signal into the board."""
    kind = _wire_type(source, target)
    if (kind == "power" and source[1].role != "power_out") or (kind in ("control", "ground") and _is_board(target) and not _is_board(source)) or (kind == "signal" and _is_board(source) and not _is_board(target)):
        source, target = target, source
    return source, target, kind


def _is_wire(entity: EngineeringEntity | None) -> bool:
    return entity is not None and entity.kind is EntityKind.CONNECTION and "source_id" in entity.metadata and entity.metadata.get("connection_type") in ELECTRICAL_TYPES


def _duplicate(graph: EngineeringGraph, first: _End, second: _End, ignore: str | None = None) -> bool:
    ends = {(first[0].id, first[1].name), (second[0].id, second[1].name)}
    return any(_is_wire(e) and e.id != ignore and {(e.metadata["source_id"], e.metadata["source_interface"]), (e.metadata["target_id"], e.metadata["target_interface"])} == ends
               for e in graph.entities.values())


def _joined(proposal: ModificationProposal, graph: EngineeringGraph, *part_ids: str) -> ModificationProposal:
    """A wire edit touches connection records, but the parts it joins are what the edit affects."""
    affected = tuple(dict.fromkeys(i for i in part_ids if i in graph.entities))
    return replace(proposal, target_ids=affected, affected_ids=affected)


def propose_wire(graph: EngineeringGraph, base: int, action: Literal["connect", "reconnect", "disconnect"], *, source: tuple[str, str] | None = None,
                 target: tuple[str, str] | None = None, connection_id: str | None = None, end: Literal["source", "target"] | None = None) -> ModificationProposal:
    """Connect two pins, move one end of a wire, or remove a wire. Electrical validity is left to verification on commit."""
    if base != len(graph.revisions): raise ValueError("stale_revision")
    if action == "connect":
        first, second, kind = _canonical(_end(graph, source), _end(graph, target))
        if _duplicate(graph, first, second): raise ModificationError("WIRE_EXISTS", "Those two pins are already wired together.", 409)
        label = f"{first[0].name} {first[1].name} to {second[0].name} {second[1].name}"
        wire = Wire(f"connection-user-wire-{uuid4().hex[:8]}", first[0].id, first[1].name, second[0].id, second[1].name, kind, label, graph.project_id)
        return _joined(snapshot_proposal(graph, base, "connect", f"Wire {label}", wire.to_ops()), graph, first[0].id, second[0].id)
    if action not in ("reconnect", "disconnect"): raise ModificationError("UNKNOWN_ACTION", f"Unknown wire action {action}.", 422)
    connection = graph.entities.get(connection_id or "")
    if connection is None: raise ModificationError("UNKNOWN_WIRE", "That wire is not in the current design.", 404)
    if not _is_wire(connection): raise ModificationError("NOT_A_WIRE", "Only electrical wires can be edited here.", 422)
    meta, edge_id = connection.metadata, f"{connection.id}-edge"
    parts = (meta["source_id"], meta["target_id"])
    remove_edge = [GraphOperation(PatchOperation.REMOVE_RELATIONSHIP, target_id=edge_id)] if edge_id in graph.relationships else []
    if action == "disconnect":
        # The relationship goes before its connection entity, so the before-image holds both and undo restores both.
        label = f"{graph.entities[parts[0]].name} {meta['source_interface']} from {graph.entities[parts[1]].name} {meta['target_interface']}"
        patch_ops = [*remove_edge, GraphOperation(PatchOperation.REMOVE_ENTITY, target_id=connection.id)]
        return _joined(snapshot_proposal(graph, base, "disconnect", f"Disconnect {label}", patch_ops), graph, *parts)
    if end not in ("source", "target"): raise ModificationError("UNKNOWN_END", "Say which end of the wire to move: source or target.", 422)
    moved = _end(graph, source if end == "source" else target)
    kept = _end(graph, (meta["target_id"], meta["target_interface"]) if end == "source" else (meta["source_id"], meta["source_interface"]))
    first, second = (moved, kept) if end == "source" else (kept, moved)
    if _duplicate(graph, first, second, ignore=connection.id): raise ModificationError("WIRE_EXISTS", "Those two pins are already wired together.", 409)
    kind = _wire_type(first, second)
    metadata = dict(meta) | {"source_id": first[0].id, "source_interface": first[1].name, "target_id": second[0].id, "target_interface": second[1].name, "connection_type": kind}
    patch_ops = [*remove_edge, GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=connection.id, changes={"metadata": metadata})]
    if remove_edge:
        # Verification re-derives nets only when a relationship is added or removed, so the edge is re-added under the same id rather than updated.
        patch_ops.append(GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=replace(graph.relationships[edge_id], source_id=first[0].id, target_id=second[0].id, type=kind)))
    summary = f"Move {end} of {connection.name or connection.id} to {moved[0].name} {moved[1].name}"
    return _joined(snapshot_proposal(graph, base, "reconnect", summary, patch_ops), graph, first[0].id, second[0].id)
