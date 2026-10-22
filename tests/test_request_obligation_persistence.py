from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json

import pytest

from aura.engineering_graph.model import EntityKind
from aura.engineering_graph.serialization import graph_to_dict
from aura.planner.live import PlanningOutcome
from aura.planner.service import PlannerService, PlannerRepairAttempt
from aura.verification.results import VerificationDecision, VerificationFinding, VerificationResult, VerificationState
from aura.workspace.server import CreateProjectBody, WorkspaceApplication


OBJECTIVE = "Build a camera slider with 400 mm travel, a lead screw, a NEMA 17 stepper motor, rails, limit switches, and a 12 V supply."


@pytest.mark.parametrize("path", ["accepted", "repaired", "diagnostic"])
def test_request_obligations_original_ledger_survives_first_commit_and_restart(tmp_path, monkeypatch, path):
    workspace = WorkspaceApplication(storage_mode="sqlite", db_path=tmp_path / "audit.db", artifact_dir=tmp_path / "artifacts")
    request = workspace._request(OBJECTIVE)
    plan = PlannerService().plan(request)
    # The provider/compiler can replace objective and invent satisfied requirements.
    # The request ledger must still derive from CreateProjectBody, not this plan.
    plan = replace(plan, request=replace(request, objective="Use a servo platform.", requirements=("Servo platform",)))
    monkeypatch.setattr(workspace, "plan", lambda body: PlanningOutcome(plan, "deterministic_test", None))
    calls = []
    def verify(candidate):
        calls.append(candidate)
        if path == "diagnostic" or (path == "repaired" and len(calls) == 1):
            finding = VerificationFinding("failure", "MISSING_DRIVE", VerificationState.FAILED,
                                          "critical", "Missing drive", (candidate.entities[0].id,), blocking=True)
            return VerificationResult(VerificationDecision.REJECT, VerificationState.FAILED, ("Missing drive",), None, (finding,))
        return VerificationResult(VerificationDecision.ACCEPT, VerificationState.CROSS_CHECKED, (), candidate.patch)
    monkeypatch.setattr("aura.workspace.server.VerificationService.verify", lambda self, candidate: verify(candidate))
    monkeypatch.setattr(PlannerService, "repair", lambda self, candidate, result: PlannerRepairAttempt(
        replace(candidate, request=replace(candidate.request, objective="Use wheels.")), {}, {"repairAttempted": True}))
    # No geometry/provider testing here. Keep real repository, graph patches and commit.
    monkeypatch.setattr(workspace.representation_service, "persist_specs", lambda project, revision, records, specs: records)
    committed = []
    save = workspace.repository.save_commit
    def capture(record, patch, verification, events):
        committed.append((graph_to_dict(record.graph), patch))
        return save(record, patch, verification, events)
    monkeypatch.setattr(workspace.repository, "save_commit", capture)
    # asyncio.run clears the global policy's current loop on Python 3.9. Keep
    # this test's execution isolated from existing synchronous asyncio tests.
    loop = asyncio.new_event_loop()
    try:
        record = loop.run_until_complete(workspace.create(CreateProjectBody(objective=OBJECTIVE)))
    finally:
        loop.close()
    expected_digest = hashlib.sha256(OBJECTIVE.encode("utf-8")).hexdigest()
    root = record.graph.get(record.project_id)
    assert "requestObligations" in root.metadata, "Original ledger absent at first commit"
    assert root.metadata["requestObjectiveDigest"] == expected_digest
    ledger = root.metadata["requestObligations"]
    assert any("400 mm" in item["originalText"] for item in ledger)
    assert any("12 V" in item["originalText"] for item in ledger)
    for item in ledger:
        assert OBJECTIVE[item["start"]:item["end"]] == item["originalText"]
    first_root = next(e for e in committed[0][0]["entities"] if e["id"] == record.project_id)
    assert first_root["metadata"]["requestObligations"] == ledger
    first_patch_root = next(op.entity for op in committed[0][1].operations if op.entity and op.entity.id == record.project_id)
    assert first_patch_root.metadata["requestObligations"] == ledger
    assert len(record.graph.revisions) == 1
    if path == "diagnostic":
        assert record.status == "build_incomplete"
        assert not record.graph.find(kind=EntityKind.COMPONENT)
    else:
        # Existing operational lifecycle retained; requested artifacts were not completed.
        assert record.status == "build_incomplete"
        assert record.graph.find(kind=EntityKind.COMPONENT)
    workspace.repository.close()
    reopened = WorkspaceApplication(storage_mode="sqlite", db_path=tmp_path / "audit.db", artifact_dir=tmp_path / "artifacts")
    stored = reopened.repository.get_project(record.project_id)
    assert stored.graph.get(record.project_id).metadata["requestObligations"] == ledger
    assert stored.graph.get(record.project_id).metadata["requestObjectiveDigest"] == expected_digest
    before = json.dumps(graph_to_dict(stored.graph), sort_keys=True)
    assert json.dumps(graph_to_dict(reopened.repository.get_project(record.project_id).graph), sort_keys=True) == before
    reopened.repository.close()
