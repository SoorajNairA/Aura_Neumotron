from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from aura.engineering_graph.model import EntityKind
from aura.infrastructure.persistence.project_repository import SQLiteProjectRepository
from aura.planner.live import PlanningOutcome
from aura.planner.schemas import ConnectionSpec
from aura.planner.service import PlannerRepairAttempt, PlannerService
from aura.workspace.server import create_app

OBJECTIVE = "Build a low-voltage fan controller"
CHILD_TABLES = ("revisions", "events", "artifacts", "work_items", "firmware_edits",
                "control_rules", "hardware_evidence", "schematic_layouts")


def _request():
    from aura.planner.schemas import ProjectRequest
    return ProjectRequest("Fan", OBJECTIVE, ("Use low-voltage control",), components=())


def _broken_plan():
    initial = PlannerService().plan(_request())
    direct = ConnectionSpec("connection-controller-fan-control", "component-controller", "component-fan", "signal-1", "signal", "control", "Unsafe direct GPIO fan control.")
    return replace(initial, connections=tuple(c for c in initial.connections if c.source_id != "component-driver" and c.target_id != "component-driver") + (direct,))


def _failed_app(monkeypatch, tmp_path):
    monkeypatch.setattr(PlannerService, "repair", lambda _self, plan, _v: PlannerRepairAttempt(plan, {"test": "unrepairable"}, {"repairAttempted": True, "repairProvider": "test"}))
    app = create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "art")
    application = app.state.workspace
    broken = _broken_plan()
    application.plan = lambda _body: PlanningOutcome(broken, "deterministic_test")
    return app, application


def _post(client, **extra):
    return client.post("/api/projects", json={"objective": OBJECTIVE, "planningMode": "deterministic_test", **extra})


def _component_count(client, project_id):
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    return sum(1 for entity in graph["entities"] if entity["kind"] == EntityKind.COMPONENT.value)


def test_empty_build_incomplete_project_is_replaced_by_fresh_plan(monkeypatch, tmp_path):
    app, application = _failed_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        failed = _post(client).json()
        assert failed["status"] == "build_incomplete" and _component_count(client, failed["projectId"]) == 0
        good = PlannerService().plan(_request())
        application.plan = lambda _body: PlanningOutcome(good, "deterministic_test")
        fresh = _post(client)
        assert fresh.status_code == 201, fresh.text
        fresh = fresh.json()
        assert fresh["projectId"] == failed["projectId"]
        assert fresh["status"] != "build_incomplete"
        assert _component_count(client, fresh["projectId"]) > 0
        assert fresh["assessment"]["planningOrigin"]["reusedProject"] is False
        assert len(client.get("/api/projects").json()) == 1
    application.repository.close()


def test_project_with_components_is_still_reused(monkeypatch, tmp_path):
    app = create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "art")
    application = app.state.workspace
    good = PlannerService().plan(_request())
    application.plan = lambda _body: PlanningOutcome(good, "deterministic_test")
    with TestClient(app) as client:
        first = _post(client).json()
        application.plan = lambda _body: (_ for _ in ()).throw(AssertionError("must not re-plan"))
        second = _post(client).json()
        assert second["projectId"] == first["projectId"] and second["createdAt"] == first["createdAt"]
        assert second["assessment"]["planningOrigin"]["reusedProject"] is True
    application.repository.close()


def test_operation_id_stays_idempotent_for_failed_project(monkeypatch, tmp_path):
    app, application = _failed_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        failed = _post(client, operationId="op-1").json()
        assert failed["status"] == "build_incomplete"
        application.plan = lambda _body: (_ for _ in ()).throw(AssertionError("same operation must not re-plan"))
        again = _post(client, operationId="op-1")
        assert again.status_code == 201
        assert again.json()["projectId"] == failed["projectId"] and again.json()["status"] == "build_incomplete"
        assert again.json()["assessment"]["planningOrigin"]["reusedProject"] is True
    application.repository.close()


def _count(repository, table, project_id):
    return repository._connection.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id=?", (project_id,)).fetchone()[0]


def test_delete_project_removes_rows_from_every_table_and_files(tmp_path):
    app = create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "art")
    repository = app.state.workspace.repository
    assert isinstance(repository, SQLiteProjectRepository)
    good = PlannerService().plan(_request())
    app.state.workspace.plan = lambda _body: PlanningOutcome(good, "deterministic_test")
    with TestClient(app) as client:
        project_id = _post(client).json()["projectId"]
    artifact = repository.create_artifact(project_id, 1, [], "test", "txt")
    artifact = repository.write_artifact(artifact.artifact_id, b"payload", "t", "1")
    path = repository.resolve_artifact_path(artifact.relative_path)
    assert path.exists()
    repository.save_work_item({"projectId": project_id, "id": "w1", "updatedAt": "now"})
    repository.save_firmware_edit(project_id, "int x;", "rev")
    repository.save_control_rules(project_id, {"a": 1})
    repository.save_layout(project_id, {"a": 1})
    repository.save_hardware_evidence(project_id, {"a": 1})
    repository.save_idea_session({"sessionId": "s1", "updatedAt": "now"})
    for table in CHILD_TABLES:
        assert _count(repository, table, project_id) >= 1, table
    repository.delete_project(project_id)
    assert repository.get_project(project_id) is None
    for table in ("projects", *CHILD_TABLES):
        assert _count(repository, table, project_id) == 0, table
    assert not path.exists()
    assert repository.get_idea_session("s1") is not None
    repository.delete_project(project_id)  # idempotent
    repository.close()
