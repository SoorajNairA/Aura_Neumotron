from __future__ import annotations

from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind, Revision
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.engineering_graph.serialization import graph_to_dict
from aura.planner.schemas import PlannedEntity, ProjectPlan, ProjectRequest, VerificationRequest
from aura.verification.results import VerificationDecision, VerificationResult, VerificationState
from aura.verification.service import VerificationService
from aura.workspace.assessment import RequestLedger, assess_workspace
from aura.workspace.representations import RepresentationRecord, RepresentationStatus
from aura.workspace.server import create_app


OBJECTIVE = "Design a low-voltage irrigation controller with a pump, container, tube, enclosure, and a 5 V power supply."


@pytest.fixture
def app(tmp_path, monkeypatch):
    application = create_app(storage_mode="sqlite", db_path=tmp_path / "workspace.db", artifact_dir=tmp_path / "artifacts")
    workspace = application.state.workspace
    # Real planners/verifiers, graph patches, transactions and HTTP routes.
    # Geometry completion is a test double; these tests make no CAD claim.
    def ready(project, revision, records, specs):
        return [replace(item, status=RepresentationStatus.READY, artifact_id="test-ready") for item in records]
    def regenerate(graph, current):
        return replace(current, revision=len(graph.revisions), status=RepresentationStatus.READY,
                       artifact_id="test-regenerated", generation=current.generation + 1)
    monkeypatch.setattr(workspace.representation_service, "persist_specs", ready)
    monkeypatch.setattr(workspace.representation_service, "regenerate", regenerate)
    monkeypatch.setattr(workspace.representation_service, "regenerate_circuit", regenerate)
    yield application
    workspace.repository.close()


def create(client):
    response = client.post("/api/projects", json={"objective": OBJECTIVE, "planningMode": "deterministic_test"})
    assert response.status_code == 201, response.text
    return response.json()


def target(client, project_id, family):
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    return next(item["id"] for item in graph["entities"] if item["metadata"].get("family") == family)


def propose(client, project, selected=None):
    response = client.post(f'/api/projects/{project["projectId"]}/modification-proposals', json={
        "projectId": project["projectId"], "baseRevision": project["revision"],
        "selectedSemanticIds": [selected or target(client, project["projectId"], "container")],
        "request": "Increase capacity while keeping height", "mode": "parameter_change"})
    assert response.status_code == 201, response.text
    return response.json()


def commit(client, project_id, proposal, key="edit"):
    response = client.post(f'/api/projects/{project_id}/modification-proposals/{proposal["proposalId"]}/commit',
                           headers={"Idempotency-Key": key})
    assert response.status_code == 200, response.text
    return response.json()


def baseline(repository, project_id):
    return [tuple(row) for row in repository._connection.execute(
        "SELECT graph_json FROM projects WHERE project_id=?", (project_id,))], [tuple(row) for row in repository._connection.execute(
        "SELECT revision_id, verification_json FROM revisions WHERE project_id=? ORDER BY revision_number", (project_id,))]


def assert_current_views(client, repository, project_id, number):
    responses = [client.get(f"/api/projects/{project_id}").json(),
                 next(item for item in client.get("/api/projects").json() if item["projectId"] == project_id),
                 client.get(f"/api/projects/{project_id}/verification").json(),
                 create(client)]
    row = repository.list_revisions(project_id)[-1]
    for response in responses:
        assessment = response["assessment"]
        assert assessment["freshness"] == "CURRENT"
        assert assessment["revisionNumber"] == response["revision"] == number == row["revision"]
        assert assessment["assessedRevisionId"] == row["revisionId"]
        for key in ("request", "softwareChecks", "limitations", "assessedRevisionId", "revisionNumber"):
            assert assessment[key] == responses[0]["assessment"][key]
    assert row["verification"]["workspaceAssessment"]["request"] == responses[0]["assessment"]["request"]
    return responses[0]["assessment"]


def test_modification_undo_and_history_assessments_bind_their_resulting_revisions(app):
    repository = app.state.workspace.repository
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        original = repository.get_project(pid).graph.get(pid).metadata
        edited = commit(client, pid, propose(client, project))
        assert edited["assessment"]["revisionNumber"] == 2
        assert edited["assessment"] == assert_current_views(client, repository, pid, 2)
        undone = client.post(f"/api/projects/{pid}/revisions/undo", headers={"Idempotency-Key": "undo"})
        assert undone.status_code == 200, undone.text
        assert undone.json()["assessment"]["revisionNumber"] == 3
        assert undone.json()["assessment"] == assert_current_views(client, repository, pid, 3)
        current = repository.get_project(pid).graph.get(pid).metadata
        for key in ("requestObligations", "requestObjectiveDigest"):
            assert current[key] == original[key]
        persisted = baseline(repository, pid)
        history = client.get(f"/api/projects/{pid}/revisions").json()
        assert [row["verification"]["workspaceAssessment"]["freshness"] for row in history] == ["STALE", "STALE", "CURRENT"]
        assert baseline(repository, pid) == persisted
        assert all(row["verification"]["workspaceAssessment"]["freshness"] == "CURRENT"
                   for row in repository.list_revisions(pid))


def test_preview_assesses_candidate_not_baseline_and_apply_assesses_exact_commit(app, monkeypatch):
    workspace = app.state.workspace; repository = workspace.repository
    seen_graphs = []
    verify = VerificationService.verify_graph
    def observe(self, graph):
        seen_graphs.append(graph_to_dict(graph))
        return verify(self, graph)
    monkeypatch.setattr(VerificationService, "verify_graph", observe)
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        power = target(client, pid, "low_voltage_power_source")
        before = baseline(repository, pid)
        scenario = client.post(f"/api/projects/{pid}/scenarios", json={"targetSemanticId": power,
            "changeType": "MODIFY_PROPERTY", "value": {"path": "parameters.voltage_v", "value": 12}})
        assert scenario.status_code == 200, scenario.text
        scenario = scenario.json()
        preview = scenario["analysis"]["assessment"]
        assert scenario["analysis"]["assessmentContext"] == "CANDIDATE_NOT_COMMITTED"
        candidate = workspace.scenarios[scenario["scenarioId"]].candidate_graph
        assert preview["assessedRevisionId"] == candidate.current_revision_id
        assert preview["request"]["missingCount"] > project["assessment"]["request"]["missingCount"]
        assert baseline(repository, pid) == before
        applied = client.post(f'/api/projects/{pid}/scenarios/{scenario["scenarioId"]}/apply')
        assert applied.status_code == 200, applied.text
        applied = applied.json(); assessment = applied["assessment"]
        stored = repository.get_project(pid)
        assert assessment["assessedRevisionId"] == applied["newRevisionId"] == stored.graph.current_revision_id
        assert assessment["assessedRevisionId"] != preview["assessedRevisionId"]
        assert assessment["request"] == preview["request"]
        assert graph_to_dict(stored.graph) in seen_graphs, "Final committed graph was not checked"
        assert assessment == assert_current_views(client, repository, pid, 2)
        # Ephemeral preview proof must not be stored as current committed proof.
        analysis = repository.list_revisions(pid)[-1]["verification"]["analysis"]
        assert "assessment" not in analysis
        assert "assessmentContext" not in analysis


def test_preview_discard_and_rejected_edit_leave_stored_baseline_untouched(app, monkeypatch):
    repository = app.state.workspace.repository
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        before = baseline(repository, pid)
        scenario = client.post(f"/api/projects/{pid}/scenarios", json={"targetSemanticId": target(client, pid, "container"),
            "changeType": "MODIFY_PROPERTY", "value": {"path": "dimensions.width.value", "value": 80}}).json()
        assert "assessment" in scenario["analysis"]
        assert client.delete(f'/api/projects/{pid}/scenarios/{scenario["scenarioId"]}').json()["discarded"]
        assert baseline(repository, pid) == before
        cancelled = propose(client, project)
        assert client.delete(f'/api/projects/{pid}/modification-proposals/{cancelled["proposalId"]}').json()["cancelled"]
        assert baseline(repository, pid) == before
        proposal = propose(client, project)
        monkeypatch.setattr(VerificationService, "verify_modification", lambda *args:
            VerificationResult(VerificationDecision.REJECT, VerificationState.FAILED, ("Rejected candidate",), None))
        rejected = client.post(f'/api/projects/{pid}/modification-proposals/{proposal["proposalId"]}/commit')
        assert rejected.status_code == 422
        assert baseline(repository, pid) == before
        assert client.get(f"/api/projects/{pid}").json()["assessment"] == {**project["assessment"],
            "planningOrigin": {**project["assessment"]["planningOrigin"], "reusedProject": None}}


def test_optimistic_conflict_and_idempotent_edit_replay_never_claim_old_assessment_current(app):
    repository = app.state.workspace.repository
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        first, conflicting = propose(client, project), propose(client, project)
        result = commit(client, pid, first)
        assert commit(client, pid, first) == result
        after = baseline(repository, pid)
        rejected = client.post(f'/api/projects/{pid}/modification-proposals/{conflicting["proposalId"]}/commit',
                               headers={"Idempotency-Key": "conflict"})
        assert rejected.status_code == 409
        assert baseline(repository, pid) == after
        undone = client.post(f"/api/projects/{pid}/revisions/undo", headers={"Idempotency-Key": "undo"}).json()
        assert client.post(f"/api/projects/{pid}/revisions/undo", headers={"Idempotency-Key": "undo"}).json() == undone
        replay = commit(client, pid, first)
        assert replay["revision"] == 2
        assert replay["assessment"]["revisionNumber"] == 2
        assert replay["assessment"]["freshness"] == "STALE"
        assert len(repository.list_revisions(pid)) == 3


def test_scenario_conflict_rejects_without_assessment_commit(app):
    repository = app.state.workspace.repository
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        selected = target(client, pid, "container")
        scenario = client.post(f"/api/projects/{pid}/scenarios", json={"targetSemanticId": selected,
            "changeType": "MODIFY_PROPERTY", "value": {"path": "dimensions.width.value", "value": 80}}).json()
        assert "assessment" in scenario["analysis"]
        commit(client, pid, propose(client, project, selected))
        after = baseline(repository, pid)
        stale = client.post(f'/api/projects/{pid}/scenarios/{scenario["scenarioId"]}/apply')
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "SCENARIO_STALE"
        assert baseline(repository, pid) == after


def test_retry_resume_recovery_preserve_original_ledger_and_immutable_assessment(app):
    repository = app.state.workspace.repository
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        stored = repository.get_project(pid)
        original = baseline(repository, pid)
        item = RepresentationRecord.from_dict(stored.representations[0])
        stuck = replace(item, status=RepresentationStatus.GENERATING, operation_id="lost-worker")
        repository.update_representations(pid, [stuck.to_dict(), *stored.representations[1:]])
        recovered = client.get(f"/api/projects/{pid}").json()
        assert recovered["representations"][0]["status"] == "fallback"
        assert recovered["assessment"]["freshness"] == "CURRENT"
        assert baseline(repository, pid) == original
        retry_url = f"/api/projects/{pid}/representations/{item.representation_id}/retry"
        retried = client.post(retry_url, headers={"Idempotency-Key": "retry"}).json()
        assert "assessment" in retried
        assert retried["assessment"]["request"] == project["assessment"]["request"]
        assert retried["assessment"]["softwareChecks"]["state"] == "NOT_RUN"
        assert client.post(retry_url, headers={"Idempotency-Key": "retry"}).json() == retried
        repository.update_project_status(pid, "build_incomplete")
        repository.update_representations(pid, [replace(item, status=RepresentationStatus.FALLBACK).to_dict(), *stored.representations[1:]])
        resumed = create(client)
        assert resumed["assessment"]["request"] == project["assessment"]["request"]
        assert resumed["assessment"]["planningOrigin"]["reusedProject"] is True
        assert baseline(repository, pid) == original
        commit(client, pid, propose(client, resumed))
        replay = client.post(retry_url, headers={"Idempotency-Key": "retry"}).json()
        assert replay["assessment"]["freshness"] == "STALE"
        assert replay["assessment"]["revisionNumber"] == 1


def test_legacy_direct_modification_persists_current_assessment(app):
    repository = app.state.workspace.repository
    with TestClient(app) as client:
        project = create(client); pid = project["projectId"]
        result = client.post(f"/api/projects/{pid}/modifications", json={"selectedComponentId": "component-driver",
            "request": "Replace with a MOSFET"})
        assert result.status_code == 200, result.text
        assert result.json()["assessment"] == assert_current_views(client, repository, pid, 2)


def structural_plan():
    request = ProjectRequest("Structure", "Use a servo.", ("Use a servo",))
    root = EngineeringEntity("structure", EntityKind.PROJECT, "Structure")
    patch = GraphPatch("structure", (GraphOperation(PatchOperation.ADD_ENTITY, entity=root),), "Structure only")
    return ProjectPlan(request, (PlannedEntity(root.id, root.kind, root.name),), (), patch, (),
                       VerificationRequest(patch.id, ()), ())


def test_explicit_structural_execution_coverage_differs_from_empty_findings():
    verified = VerificationService().verify(structural_plan())
    coverage = getattr(verified, "execution_coverage", None)
    assert coverage is not None, "Verifier does not record actual execution coverage"
    assert coverage.applicability_known
    assert set(coverage.executed_check_ids) == {"PLAN_SCHEMA", "PLAN_SOLE_PROJECT"}
    assert set(coverage.applicable_check_ids) == set(coverage.executed_check_ids)
    assert "ENGINEERING_PLAN_RULES" in coverage.not_applicable_check_ids
    assert not coverage.not_evaluated_check_ids
    inputs = dict(operational_status="ready", assessed_revision_id="revision-1", revision_number=1,
                  current_revision_id="revision-1", current_revision_number=1, verification=verified)
    assert assess_workspace(**inputs).software_checks.state.value == "NOT_RUN"
    assert assess_workspace(**inputs, check_coverage=coverage).software_checks.state.value == "PASSED"
    assert assess_workspace(**inputs, check_coverage=coverage).engineering_evidence.state.value == "NOT_VERIFIED"


def test_graph_dispatch_execution_does_not_claim_per_rule_applicability_from_zero_findings():
    graph = EngineeringGraph("graph", entities={"graph": EngineeringEntity("graph", EntityKind.PROJECT, "Graph")})
    verified = VerificationService().verify_graph(graph)
    assert not verified.findings
    coverage = getattr(verified, "execution_coverage", None)
    assert coverage is not None
    assert set(coverage.executed_check_ids) == {"GRAPH_SCHEMA", "GRAPH_RULE_DISPATCH"}
    assert not coverage.applicability_known
    assert "GRAPH_RULE_APPLICABILITY" in coverage.not_evaluated_check_ids
    assert verified.accepted
    assert assess_workspace(operational_status="ready", assessed_revision_id="revision-1", revision_number=1,
        current_revision_id="revision-1", current_revision_number=1, verification=verified,
        check_coverage=coverage).software_checks.state.value == "NOT_RUN"


def test_early_schema_failure_does_not_claim_later_checks_ran():
    plan = structural_plan()
    verified = VerificationService().verify(replace(plan, request=replace(plan.request, requirements=())))
    coverage = getattr(verified, "execution_coverage", None)
    assert coverage is not None
    assert coverage.executed_check_ids == ("PLAN_SCHEMA",)
    assert "PLAN_SOLE_PROJECT" in coverage.not_evaluated_check_ids
    assert "ENGINEERING_PLAN_RULES" not in coverage.executed_check_ids
    assert verified.state is VerificationState.FAILED


def test_graph_schema_failure_binds_finding_and_failed_assessment_to_checked_revision():
    graph = EngineeringGraph("graph", revisions=[Revision("revision-1", None, "patch-1", "Initial"),
                                                Revision("revision-2", "revision-1", "patch-2", "Later")])
    verified = VerificationService().verify_graph(graph)
    assert verified.state is VerificationState.FAILED
    assert verified.findings[0].revision == 2
    assessment = assess_workspace(operational_status="ready", assessed_revision_id=graph.current_revision_id,
        revision_number=2, current_revision_id=graph.current_revision_id, current_revision_number=2,
        verification=verified, check_coverage=verified.execution_coverage)
    assert assessment.software_checks.state.value == "FAILED"


def test_original_ledger_roundtrip_validates_original_text_and_digest():
    from aura.workspace.assessment import collect_request_obligations
    ledger = collect_request_obligations(OBJECTIVE)
    assert hasattr(RequestLedger, "from_dict"), "Stored original ledger cannot be restored"
    assert RequestLedger.from_dict(json.loads(json.dumps(ledger.to_dict()))) == ledger
    damaged = ledger.to_dict(); damaged["obligations"][0]["originalText"] = "planner replacement"
    with pytest.raises(ValueError): RequestLedger.from_dict(damaged)
    damaged = ledger.to_dict(); damaged["objectiveDigest"] = "invented-digest"
    with pytest.raises(ValueError): RequestLedger.from_dict(damaged)
