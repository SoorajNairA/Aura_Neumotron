import json

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.model import EngineeringEntity, EntityKind, Relationship
from aura.engineering_graph.patches import GraphOperation, PatchOperation
from aura.engineering_graph.serialization import graph_from_dict, graph_to_dict
from aura.verification.service import VerificationService
from aura.workspace.bridge import WorkspaceBridge
from aura.workspace.edits import snapshot_proposal
from aura.workspace.modifications import inverse_proposal
from aura.workspace.server import create_app


@pytest.fixture()
def seeded(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        pid = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()["projectId"]
        yield graph_from_dict(client.get(f"/api/projects/{pid}/graph").json())


def settled(graph):
    """graph_to_dict minus revisions and the evidence/verification records, which a commit marks stale (by design, until re-verified)."""
    g = json.loads(json.dumps(graph_to_dict(graph)))
    return {k: ([e for e in v if e["kind"] not in ("evidence", "verification_result")] if k == "entities" else v) for k, v in g.items() if k != "revisions"}


def commit(graph, proposal):
    """Verify and commit as the server does; returns the new graph and the revision dict undo reads."""
    result = VerificationService().verify_modification(graph, proposal.patch)
    assert result.accepted, result.reasons
    updated = WorkspaceBridge().commit(graph, result)
    diff = {"changed": list(proposal.operations), "regenerated": list(proposal.regenerate), "affected": list(proposal.affected_ids), "unchanged": list(proposal.unaffected)}
    return updated, {"patch": result.patch, "verification": {"diff": diff}}


def rename(graph, name="Renamed controller"):
    controller = graph.get("component-controller")
    return snapshot_proposal(graph, len(graph.revisions), "edit", f"Rename to {name}",
                             [GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=controller.id, changes={"name": name})])


def test_snapshot_commit_then_undo_restores_graph(seeded):
    before = settled(seeded)
    updated, revision = commit(seeded, rename(seeded))
    assert updated.get("component-controller").name == "Renamed controller"
    undo = inverse_proposal(updated, revision)
    assert undo.mode == "undo"
    restored, _ = commit(updated, undo)
    assert settled(restored) == before


def test_snapshot_records_added_ids(seeded):
    controller = seeded.get("component-controller")
    part = EngineeringEntity("component-user-new", EntityKind.COMPONENT, "New", controller.parent_id, {"family": "x"})
    wire = Relationship("wire-user-new", part.id, controller.id, "mechanical", {})
    proposal = snapshot_proposal(seeded, len(seeded.revisions), "add", "Add New", [
        GraphOperation(PatchOperation.ADD_ENTITY, entity=part), GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=wire),
        GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=controller.id, changes={"name": "Brain"})])
    op = proposal.operations[0]
    assert op["operation"] == "snapshot_edit" and op["mode"] == "add"
    assert op["addedEntityIds"] == [part.id] and op["addedRelationshipIds"] == [wire.id]
    assert [e["id"] for e in op["before"]["entities"]] == [controller.id]
    assert op["before"]["entities"][0]["name"] == controller.name and op["before"]["relationships"] == []
    assert part.id in proposal.affected_ids and controller.id in proposal.affected_ids
    assert proposal.regenerate == ("firmware",) and proposal.verification["outcome"] == "pending_graph_verification"
    json.dumps(proposal.operations)  # stored in the revision, so it must be JSON-pure
    updated, revision = commit(seeded, proposal)
    assert part.id in updated.entities and wire.id in updated.relationships
    restored, _ = commit(updated, inverse_proposal(updated, revision))
    assert part.id not in restored.entities and wire.id not in restored.relationships
    assert settled(restored) == settled(seeded)


def test_undo_of_snapshot_with_removed_entity_restores_it(seeded):
    # Remove one wire's connection entity and its relationship; undo must bring both back.
    rel = next(r for r in seeded.relationships.values() if r.metadata.get("connection_id") in seeded.entities)
    connection_id = rel.metadata["connection_id"]
    proposal = snapshot_proposal(seeded, len(seeded.revisions), "remove", "Remove a wire", [
        GraphOperation(PatchOperation.REMOVE_RELATIONSHIP, target_id=rel.id), GraphOperation(PatchOperation.REMOVE_ENTITY, target_id=connection_id)])
    updated, revision = commit(seeded, proposal)
    assert rel.id not in updated.relationships and connection_id not in updated.entities
    restored, _ = commit(updated, inverse_proposal(updated, revision))
    assert restored.entities[connection_id] == seeded.entities[connection_id]
    assert restored.relationships[rel.id] == seeded.relationships[rel.id]
    assert settled(restored) == settled(seeded)


def test_undo_of_undo_redoes_the_edit(seeded):
    updated, revision = commit(seeded, rename(seeded))
    undone, undo_revision = commit(updated, inverse_proposal(updated, revision))
    redone, _ = commit(undone, inverse_proposal(undone, undo_revision))
    assert redone.get("component-controller").name == "Renamed controller"


def test_undo_of_snapshot_that_added_wired_part_drops_its_nets(seeded):
    from aura.workspace.modifications import propose_add_components
    ops = list(propose_add_components(seeded, len(seeded.revisions), ["ds18b20-module"]).patch.operations)
    proposal = snapshot_proposal(seeded, len(seeded.revisions), "add", "Add DS18B20", ops)
    updated, revision = commit(seeded, proposal)
    part_id = proposal.operations[0]["addedEntityIds"][0]
    assert any(part_id in str(e.metadata.get("terminals")) for e in updated.entities.values() if e.metadata.get("semantic_type") == "electrical_net")
    restored, _ = commit(updated, inverse_proposal(updated, revision))
    assert part_id not in restored.entities
    assert not any(part_id in str(e.metadata.get("terminals")) for e in restored.entities.values())
    assert settled(restored) == settled(seeded)
