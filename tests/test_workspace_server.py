from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from aura.planner.live import LivePlanner
from aura.planner.schemas import ProjectRequest
from aura.workspace.server import create_app


OBJECTIVE = "Design a small ESP32-based automatic plant irrigation system with sensor, pump, driver, power, tubing, reservoir, and enclosure."


class FakeProvider:
    def __init__(self, responses, delay=0): self.responses=list(responses); self.delay=delay; self.prompts=[]
    def generate(self, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        if self.delay: time.sleep(self.delay)
        return self.responses.pop(0)
    def stream_generate(self, *args, **kwargs): return iter(())
    def is_available(self): return True
    def get_diagnostics(self): return {"backend":"fake"}


VALID = json.dumps({"projectName":"Automatic Irrigation System","objective":OBJECTIVE,
    "requirements":["Use low voltage"],"assumptions":["Enclosure separates water"],
    "components":["ESP32","soil sensor","pump","relay driver","power source","tubing","reservoir","enclosure"]})


@pytest.mark.unit
def test_live_planner_repairs_once_and_rejects_malformed_output() -> None:
    request = ProjectRequest("Automatic Irrigation System", OBJECTIVE, ("Use low voltage",))
    repaired_provider = FakeProvider(["not json", VALID])
    repaired = LivePlanner(repaired_provider, 1).plan(request)
    assert repaired.mode == "live_model"
    assert len(repaired_provider.prompts) == 2 and "validation errors" in repaired_provider.prompts[1]
    malformed = LivePlanner(FakeProvider(["bad", "still bad"]), 1).plan(request)
    assert malformed.mode == "deterministic_fallback"
    assert "invalid after repair" in malformed.fallback_reason


@pytest.mark.unit
def test_live_planner_timeout_uses_honest_fallback() -> None:
    request = ProjectRequest("Automatic Irrigation System", OBJECTIVE, ("Use low voltage",))
    outcome = LivePlanner(FakeProvider([VALID], delay=.1), .01).plan(request)
    assert outcome.mode == "deterministic_fallback"
    assert "timed out" in outcome.fallback_reason


def create_project(client: TestClient, mode="deterministic_test"):
    response = client.post("/api/projects", json={"objective":OBJECTIVE,"planningMode":mode})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.integration
def test_project_graph_revision_and_frontend_apis() -> None:
    app = create_app()
    with TestClient(app) as client:
        project = create_project(client)
        assert project["planningMode"] == "deterministic_test"
        project_id = project["projectId"]
        graph = client.get(f"/api/projects/{project_id}/graph").json()
        assert any(item["id"] == "component-esp32" for item in graph["entities"])
        assert len(client.get(f"/api/projects/{project_id}/revisions").json()) == 1
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        assert all(item["fallbackType"] == "placeholder" for item in project["representations"])


@pytest.mark.integration
def test_websocket_order_and_replay_after_event_id() -> None:
    app = create_app()
    with TestClient(app) as client:
        project_id = create_project(client)["projectId"]
        history = app.state.workspace.broker.events[project_id]
        with client.websocket_connect(f"/api/projects/{project_id}/events?afterEventId=0") as socket:
            received = [socket.receive_json() for _ in history]
        assert [item["eventId"] for item in received] == list(range(1, len(received)+1))
        types = [item["type"] for item in received]
        assert types.index("component.added") < types.index("verification.started")
        assert types.index("warning.created") < types.index("verification.completed")
        after = received[-3]["eventId"]
        with client.websocket_connect(f"/api/projects/{project_id}/events?afterEventId={after}") as socket:
            replay = [socket.receive_json() for _ in range(2)]
        assert [item["eventId"] for item in replay] == [after+1, after+2]


@pytest.mark.integration
def test_modification_endpoint_is_partial_and_revalidated() -> None:
    app = create_app()
    with TestClient(app) as client:
        project_id = create_project(client)["projectId"]
        response = client.post(f"/api/projects/{project_id}/modifications", json={
            "selectedComponentId":"component-driver",
            "request":"Replace the relay with a logic-level MOSFET driver."})
        assert response.status_code == 200
        summary = response.json()
        assert summary["before"]["id"] == summary["after"]["id"] == "component-driver"
        assert summary["rerunChecks"] == ["driver-update"]
        graph = client.get(f"/api/projects/{project_id}/graph").json()
        driver = next(item for item in graph["entities"] if item["id"] == "component-driver")
        assert driver["name"] == "Logic-level MOSFET driver"
        assert len(client.get(f"/api/projects/{project_id}/revisions").json()) == 2


@pytest.mark.integration
def test_live_mode_metadata_and_fallback_event() -> None:
    app = create_app(provider=FakeProvider(["bad", "bad"]))
    with TestClient(app) as client:
        project = create_project(client, "live_model")
        assert project["planningMode"] == "deterministic_fallback"
        assert project["fallbackReason"]
        types = [event.type for event in app.state.workspace.broker.events[project["projectId"]]]
        assert "task.fallback_used" in types


@pytest.mark.unit
def test_server_import_does_not_load_heavy_optional_systems() -> None:
    import subprocess, sys
    code="import sys; import aura.workspace.server; assert not any(x in sys.modules for x in ['PySide6','torch','TTS','aura.unreal_domain'])"
    result=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr
