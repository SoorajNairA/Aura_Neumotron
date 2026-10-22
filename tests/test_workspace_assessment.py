from __future__ import annotations

from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation, apply_patch
from aura.infrastructure.persistence.project_repository import StoredProject
from aura.planner.live import PlanningOutcome
from aura.planner.service import PlannerService, PlannerRepairAttempt
from aura.verification.results import VerificationDecision, VerificationResult, VerificationState
from aura.workspace.assessment import WorkspaceAssessment
from aura.workspace.representations import RepresentationRecord, RepresentationStatus, RepresentationType
from aura.workspace.server import create_app, _project_payload


OBJECTIVE = "Build a camera slider with a lead screw, rails, carriage, a NEMA 17 stepper motor, limit switches, 400 mm travel, and a 12 V supply."
LIMITATION = "Creation checks do not establish actuator mounting or physical validity"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    app = create_app(storage_mode="sqlite", db_path=tmp_path / "workspace.db", artifact_dir=tmp_path / "artifacts")
    application = app.state.workspace
    plan = PlannerService().plan(application._request(OBJECTIVE))
    monkeypatch.setattr(application, "plan", lambda body: PlanningOutcome(plan, "deterministic_test", None))
    monkeypatch.setattr("aura.workspace.server.VerificationService.verify", lambda self, candidate:
                        VerificationResult(VerificationDecision.ACCEPT, VerificationState.CROSS_CHECKED,
                                           (LIMITATION,), candidate.patch))
    # Exercise actual graph commits, SQLite and routes, without geometry or model calls.
    monkeypatch.setattr(application.representation_service, "persist_specs", lambda project, revision, records, specs: records)
    yield app
    application.repository.close()


def create(client, **extra):
    response = client.post("/api/projects", json={"objective": OBJECTIVE, "planningMode": "deterministic_test", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def views(client, project_id):
    return [client.get(f"/api/projects/{project_id}").json(),
            next(row for row in client.get("/api/projects").json() if row["projectId"] == project_id),
            client.get(f"/api/projects/{project_id}/verification").json()]


def test_creation_assessment_commits_atomically_with_real_revision_and_matches_all_views(workspace, monkeypatch):
    repository = workspace.state.workspace.repository
    save = repository.save_commit
    supplied = []
    def capture(record, patch, verification, events):
        snapshot = verification["workspaceAssessment"]
        assert snapshot["assessedRevisionId"] == record.graph.current_revision_id
        assert snapshot["revisionNumber"] == len(record.graph.revisions) == 1
        assert not repository.list_revisions(record.project_id)
        supplied.append(snapshot)
        return save(record, patch, verification, events)
    monkeypatch.setattr(repository, "save_commit", capture)
    with TestClient(workspace) as client:
        created = create(client)
        assessment = created["assessment"]
        rows = repository.list_revisions(created["projectId"])
        assert len(rows) == 1
        stored = rows[0]["verification"]["workspaceAssessment"]
        assert stored == supplied[0]
        assert assessment["assessedRevisionId"] == rows[0]["revisionId"]
        assert assessment["revisionNumber"] == rows[0]["revision"] == 1
        assert assessment["request"]["missingCount"] > 0
        assert assessment["request"]["unassessedCount"] > 0
        assert assessment["request"]["state"] != "FULFILLED"
        assert assessment["softwareChecks"]["state"] == "NOT_RUN"
        assert LIMITATION in assessment["limitations"]
        for response in views(client, created["projectId"]):
            current = response["assessment"]
            for key in ("request", "assessedRevisionId", "revisionNumber", "freshness", "limitations", "softwareChecks"):
                assert current[key] == assessment[key]
        assert {"status", "planningMode", "fallbackReason", "representations", "revision"} <= created.keys()
        verification = views(client, created["projectId"])[-1]
        assert {"summary", "findings", "evidence", "revision"} <= verification.keys()
        # Deserialization roundtrip preserves the separate meanings.
        assert WorkspaceAssessment.from_dict(json.loads(json.dumps(stored))).to_dict() == stored


def test_read_overlay_keeps_ready_status_proxy_and_immutable_creation_limits(workspace):
    application = workspace.state.workspace
    repository = application.repository
    with TestClient(workspace) as client:
        created = create(client)
        project_id = created["projectId"]
        stored = repository.list_revisions(project_id)[0]["verification"]["workspaceAssessment"]
        record = repository.get_project(project_id)
        records = [replace(RepresentationRecord.from_dict(item), status=RepresentationStatus.READY,
                           artifact_id="test-artifact") for item in record.representations]
        repository.update_representations(project_id, [item.to_dict() for item in records])
        repository.update_project_status(project_id, "ready")
        for response in views(client, project_id):
            assessment = response["assessment"]
            assert assessment["operationalStatus"] == "ready"
            assert assessment["request"] == stored["request"]
            assert assessment["softwareChecks"]["state"] == "NOT_RUN"
            assert LIMITATION in assessment["limitations"]
            mechanical = [item for item in assessment["representations"] if item["representationType"] == "mechanical_3d"]
            assert mechanical
            assert all(item["kind"] == "PROCEDURAL_PROXY" and item["artifactState"] == "READY"
                       and item["cadEvaluationState"] == "NOT_RUN" for item in mechanical)
        assert repository.list_revisions(project_id)[0]["verification"]["workspaceAssessment"] == stored


def test_later_empty_graph_result_leaves_original_missing_obligations_stale(workspace):
    repository = workspace.state.workspace.repository
    with TestClient(workspace) as client:
        created = create(client)
        project_id = created["projectId"]
        original = created["assessment"]
        record = repository.get_project(project_id)
        patch = GraphPatch("later-check", (GraphOperation(PatchOperation.ADD_ENTITY,
            entity=EngineeringEntity("later-note", EntityKind.PROJECT, "Later note")),),
            "Uncovered subsequent revision", base_revision_id=record.graph.current_revision_id)
        graph = apply_patch(record.graph, patch)
        repository.save_commit(replace(record, graph=graph), patch,
                               {"state": "cross_checked", "decision": "accept", "findings": []}, [])
        responses = views(client, project_id)
        assert responses[0]["assessment"]["softwareChecks"] == responses[1]["assessment"]["softwareChecks"] == responses[2]["assessment"]["softwareChecks"]
        for response in responses:
            assessment = response["assessment"]
            assert assessment["freshness"] == "STALE"
            assert assessment["request"]["state"] == "STALE"
            for key in ("missingCount", "unassessedCount", "obligations"):
                assert assessment["request"][key] == original["request"][key]
            assert assessment["assessedRevisionId"] == original["assessedRevisionId"]
            assert assessment["revisionNumber"] == 1
            assert LIMITATION in assessment["limitations"]
            assert assessment["softwareChecks"]["state"] != "PASSED"


@pytest.mark.parametrize("generating", [False, True])
def test_legacy_reads_are_conservative_and_never_write_database(workspace, generating):
    repository = workspace.state.workspace.repository
    patch = GraphPatch("legacy", (GraphOperation(PatchOperation.ADD_ENTITY,
        entity=EngineeringEntity("legacy-project", EntityKind.PROJECT, "Legacy")),), "Legacy project")
    graph = apply_patch(EngineeringGraph("legacy-project"), patch)
    representations = []
    if generating:
        representations = [RepresentationRecord("legacy-rep", "legacy-project", 1, ("legacy-project",),
            RepresentationType.MECHANICAL_3D, RepresentationStatus.GENERATING, "old", "1",
            operation_id="lost-worker").to_dict()]
    record = StoredProject("legacy-project", "Use a servo.", "deterministic_test", None, "ready", graph,
                           representations, "then", "then")
    repository.save_commit(record, patch, {"state": "cross_checked", "findings": []}, [])
    before = list(repository._connection.iterdump())
    with TestClient(workspace) as client:
        for _ in range(2):
            for response in views(client, record.project_id):
                assessment = response["assessment"]
                assert assessment["request"]["state"] == "NOT_ASSESSED"
                assert assessment["softwareChecks"]["state"] == "NOT_RUN"
                assert assessment["assessedRevisionId"] is None
                assert assessment["operationalStatus"] == "ready"
        assert list(repository._connection.iterdump()) == before
    assert _project_payload(record)["assessment"]["request"]["state"] == "NOT_ASSESSED"


def test_cached_deterministic_create_cannot_claim_fresh_live_planning(workspace, monkeypatch):
    application = workspace.state.workspace
    with TestClient(workspace) as client:
        first = create(client)
        project_id = first["projectId"]
        snapshot = application.repository.list_revisions(project_id)[0]["verification"]["workspaceAssessment"]
        monkeypatch.setattr(application, "plan", lambda body: pytest.fail("Cached project must not call a provider"))
        repeated = create(client, planningMode="live_model")
        origin = repeated["assessment"]["planningOrigin"]
        assert origin["planningMode"] == repeated["planningMode"] == "deterministic_test"
        assert origin["provider"] == "deterministic"
        assert origin["reusedProject"] is True
        assert first["assessment"]["planningOrigin"]["reusedProject"] is False
        assert len(application.repository.list_revisions(project_id)) == 1
        assert application.repository.list_revisions(project_id)[0]["verification"]["workspaceAssessment"] == snapshot


def test_ledger_only_legacy_project_does_not_recover_artifacts_during_get(workspace):
    repository = workspace.state.workspace.repository
    with TestClient(workspace) as client:
        created = create(client)
        project_id = created["projectId"]
        verification = repository.list_revisions(project_id)[0]["verification"]
        verification.pop("workspaceAssessment")
        with repository._connection:
            repository._connection.execute("UPDATE revisions SET verification_json=? WHERE project_id=?",
                                           (json.dumps(verification), project_id))
        record = repository.get_project(project_id)
        records = [replace(RepresentationRecord.from_dict(item), status=RepresentationStatus.GENERATING,
                           operation_id="lost-worker").to_dict() for item in record.representations]
        repository.update_representations(project_id, records)
        before = list(repository._connection.iterdump())
        for response in views(client, project_id):
            assert response["assessment"]["request"]["state"] == "NOT_ASSESSED"
            assert response["assessment"]["softwareChecks"]["state"] == "NOT_RUN"
        assert list(repository._connection.iterdump()) == before


def test_diagnostic_first_commit_has_bound_assessment(workspace, monkeypatch):
    application = workspace.state.workspace
    failed = VerificationResult(VerificationDecision.REJECT, VerificationState.FAILED, ("Architecture rejected",), None)
    monkeypatch.setattr("aura.workspace.server.VerificationService.verify", lambda self, plan: failed)
    monkeypatch.setattr(PlannerService, "repair", lambda self, plan, result:
                        PlannerRepairAttempt(plan, {}, {"repairAttempted": True}))
    with TestClient(workspace) as client:
        created = create(client)
        row = application.repository.list_revisions(created["projectId"])[0]
        assert created["status"] == "build_incomplete"
        assert row["verification"]["workspaceAssessment"]["assessedRevisionId"] == row["revisionId"]
        assert created["assessment"]["softwareChecks"]["state"] == "FAILED"
        assert created["assessment"]["request"]["missingCount"] > 0


def test_assessment_rolls_back_with_project_revision_and_events(workspace, monkeypatch):
    repository = workspace.state.workspace.repository
    save = repository.save_commit
    def fail_after_revision(record, patch, verification, events):
        assert verification["workspaceAssessment"]["assessedRevisionId"] == record.graph.current_revision_id
        # Missing event type fails after the revision INSERT inside the existing transaction.
        return save(record, patch, verification, [{}])
    monkeypatch.setattr(repository, "save_commit", fail_after_revision)
    with TestClient(workspace) as client:
        response = client.post("/api/projects", json={"objective": OBJECTIVE, "planningMode": "deterministic_test"})
        assert response.status_code == 503
    assert repository.list_projects() == []
    assert repository._connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 0
    assert repository._connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


@pytest.mark.parametrize("damage", ["revision", "version", "counts", "no_coverage"])
def test_invalid_persisted_assessment_is_conservative_without_read_repair(workspace, damage):
    repository = workspace.state.workspace.repository
    with TestClient(workspace) as client:
        created = create(client)
        project_id = created["projectId"]
        verification = repository.list_revisions(project_id)[0]["verification"]
        snapshot = verification["workspaceAssessment"]
        if damage == "revision": snapshot["assessedRevisionId"] = "invented-revision"
        elif damage == "version": snapshot["assessmentVersion"] = 999
        elif damage == "counts": snapshot["request"]["missingCount"] = -1
        else: snapshot["softwareChecks"]["state"] = "PASSED"
        with repository._connection:
            repository._connection.execute("UPDATE revisions SET verification_json=? WHERE project_id=?",
                                           (json.dumps(verification), project_id))
        before = list(repository._connection.iterdump())
        for response in views(client, project_id):
            assessment = response["assessment"]
            assert assessment["request"]["state"] == "NOT_ASSESSED"
            assert assessment["softwareChecks"]["state"] == "NOT_RUN"
            assert assessment["limitations"]
        assert list(repository._connection.iterdump()) == before
