from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
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


@pytest.mark.unit
def test_repeated_planner_timeouts_use_a_bounded_worker_pool() -> None:
    request=ProjectRequest("Automatic Irrigation System",OBJECTIVE,("Use low voltage",))
    for _ in range(12):
        outcome=LivePlanner(FakeProvider([VALID],delay=.2),.005).plan(request)
        assert outcome.mode=="deterministic_fallback"

    planner_threads=[thread for thread in threading.enumerate() if thread.name.startswith("aura-planner")]
    assert len(planner_threads)<=4


def create_project(client: TestClient, mode="deterministic_test"):
    response = client.post("/api/projects", json={"objective":OBJECTIVE,"planningMode":mode})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.integration
def test_repeating_create_resumes_failed_representation_without_new_revision(tmp_path) -> None:
    app=create_app(storage_mode="sqlite",db_path=tmp_path/"workspace.db",artifact_dir=tmp_path/"artifacts")
    repository=app.state.workspace.repository
    write_artifact=repository.write_artifact
    failed=False

    def fail_first_write(*args,**kwargs):
        nonlocal failed
        if not failed:
            failed=True
            raise OSError("disk full")
        return write_artifact(*args,**kwargs)

    repository.write_artifact=fail_first_write
    with TestClient(app) as client:
        first=create_project(client)
        failed_id=next(item["representationId"] for item in first["representations"] if item["status"]=="fallback")
        repository.write_artifact=write_artifact

        retried=create_project(client)

        assert retried["projectId"]==first["projectId"]
        assert retried["revision"]==first["revision"]==1
        recovered=next(item for item in retried["representations"] if item["representationId"]==failed_id)
        assert recovered["status"]=="ready"
        assert recovered["artifactId"]


@pytest.mark.integration
def test_project_graph_revision_and_frontend_apis() -> None:
    app = create_app(storage_mode="memory")
    with TestClient(app) as client:
        project = create_project(client)
        assert project["planningMode"] == "deterministic_test"
        project_id = project["projectId"]
        graph = client.get(f"/api/projects/{project_id}/graph").json()
        assert any(dict(item["metadata"]).get("family") == "microcontroller_board" for item in graph["entities"])
        assert len(client.get(f"/api/projects/{project_id}/revisions").json()) == 1
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 404
        assert client.get("/assets/index.html").status_code == 404
        assert client.get("/assets/representation/index.html").status_code == 200
        assert all(item["fallbackType"] == "placeholder" for item in project["representations"])


@pytest.mark.integration
def test_websocket_order_and_replay_after_event_id() -> None:
    app = create_app(storage_mode="memory")
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
def test_installed_server_accepts_a_real_websocket_upgrade() -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = dict(os.environ, AURA_WORKSPACE_STORAGE_MODE="memory")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "aura.workspace.server:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=.2):
                    break
            except OSError:
                if process.poll() is not None:
                    pytest.fail(process.stderr.read())
                time.sleep(.05)
        else:
            pytest.fail("Uvicorn did not start within 10 seconds")

        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            client.sendall(
                b"GET /api/projects/probe/events?afterEventId=0 HTTP/1.1\r\n"
                + f"Host: 127.0.0.1:{port}\r\n".encode()
                + b"Connection: Upgrade\r\nUpgrade: websocket\r\n"
                + b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                + b"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            response = client.recv(4096)
        assert response.startswith(b"HTTP/1.1 101"), response
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.integration
def test_modification_endpoint_is_partial_and_revalidated() -> None:
    app = create_app(storage_mode="memory")
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
    app = create_app(provider=FakeProvider(["bad", "bad"]), storage_mode="memory")
    with TestClient(app) as client:
        project = create_project(client, "live_model")
        assert project["planningMode"] == "deterministic_fallback"
        assert project["fallbackReason"]
        types = [event.type for event in app.state.workspace.broker.events[project["projectId"]]]
        assert "task.fallback_used" in types


@pytest.mark.integration
def test_repeated_live_create_reuses_persisted_project_without_replanning() -> None:
    provider=FakeProvider([VALID])
    app=create_app(provider=provider,storage_mode="memory")
    with TestClient(app) as client:
        # The persisted project must have components: a component-less build_incomplete project is replanned, not reused.
        first=client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"deterministic_test"})
        assert first.json()["status"]!="build_incomplete"
        prompts_after_first=len(provider.prompts)
        second=client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"live_model"})
        assert first.status_code==second.status_code==201
        assert first.json()["projectId"]==second.json()["projectId"]
        assert len(provider.prompts)==prompts_after_first
        assert len(client.get(f"/api/projects/{first.json()['projectId']}/revisions").json())==1


@pytest.mark.integration
def test_pathological_and_malformed_create_inputs_fail_boundedly() -> None:
    app=create_app(storage_mode="memory")
    with TestClient(app) as client:
        assert client.post("/api/projects",json={"objective":"make a 99999-axis robot","planningMode":"deterministic_test"}).status_code==422
        assert client.post("/api/projects",json={"objective":"x"*2001,"planningMode":"deterministic_test"}).status_code==422
        assert client.post("/api/projects",json={"objective":"make a desk fan","planningMode":"unknown"}).status_code==422


@pytest.mark.integration
def test_concurrent_duplicate_create_commits_one_revision() -> None:
    from concurrent.futures import ThreadPoolExecutor
    app=create_app(storage_mode="memory")
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        create=lambda:client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"deterministic_test"})
        responses=[future.result() for future in (pool.submit(create),pool.submit(create))]
        assert all(response.status_code==201 for response in responses)
        ids={response.json()["projectId"] for response in responses}
        assert len(ids)==1
        assert len(client.get(f"/api/projects/{ids.pop()}/revisions").json())==1


@pytest.mark.unit
def test_server_import_does_not_load_heavy_optional_systems() -> None:
    code="""
import sys
import aura
import aura.main
import aura.workspace.server
blocked = [name for name in sys.modules if name.startswith('aura.legacy')]
blocked += [name for name in ('PySide6','torch','TTS','aura.infrastructure.desktop.computer_operator','aura.infrastructure.voice.tts') if name in sys.modules]
assert not blocked, blocked
"""
    result=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr
