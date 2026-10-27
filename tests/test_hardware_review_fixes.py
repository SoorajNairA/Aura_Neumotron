import json
import os
import threading
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import aura.hardware.serial as serial_module
from aura.firmware.compile import CompileResult
from aura.hardware.serial import SerialSession, parse_line
from aura.workspace.server import create_app
from tests.test_hardware_serial import FakeProcess, wait_for

FAN = "Build a temperature-controlled desk fan"


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_FAKE_BOARD", "1")
    monkeypatch.setattr("aura.workspace.server.compile_sketch", lambda a, **kw: CompileResult("passed", (), 1, a.revision_id, datetime.now(timezone.utc).isoformat(), ""))
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        yield client


def project(client, objective=FAN):
    return client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()["projectId"]


def alive(name):
    return [t for t in threading.enumerate() if t.name == name and t.is_alive()]


def test_concurrent_starts_leave_one_session_and_stop_ends_it(app_client):
    pid = project(app_client)
    threads = [threading.Thread(target=lambda: app_client.post(f"/api/projects/{pid}/serial/start", json={"port": "FAKE0"})) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert wait_for(lambda: len(alive("serial-FAKE0")) == 1)
    app_client.post(f"/api/projects/{pid}/serial/stop")
    assert wait_for(lambda: not alive("serial-FAKE0")) and app_client.app.state.hardware_busy_ports == {}


def test_a_monitor_that_exited_does_not_hold_the_port(app_client, monkeypatch):
    pid = project(app_client)
    monkeypatch.setattr("aura.workspace.server.find_cli", lambda: "arduino-cli")
    monkeypatch.setattr("aura.hardware.serial.subprocess.Popen", lambda args, **kw: FakeProcess(b"bye\n"))
    app_client.post(f"/api/projects/{pid}/serial/start", json={"port": "COM7"})
    assert wait_for(lambda: app_client.get(f"/api/projects/{pid}/serial?after=0").json()["running"] is False)
    monkeypatch.setattr("aura.workspace.server.upload_sketch", lambda artifact, port: __import__("aura.hardware.upload", fromlist=["UploadResult"]).UploadResult("uploaded", port, artifact.revision_id, "t"))
    app_client.post(f"/api/projects/{pid}/firmware/compile")
    assert app_client.post(f"/api/projects/{pid}/firmware/upload", json={"port": "COM7"}).json()["status"] == "uploaded"


def test_an_upload_blocks_monitors_and_uploads_on_that_port_from_other_projects(app_client, monkeypatch):
    first, second = project(app_client), project(app_client, "Build a temperature-controlled desk fan for the bedroom")
    release = threading.Event()
    from aura.hardware.upload import UploadResult
    monkeypatch.setattr("aura.workspace.server.upload_sketch", lambda artifact, port: release.wait(5) and UploadResult("uploaded", port, artifact.revision_id, "t"))
    for pid in (first, second): app_client.post(f"/api/projects/{pid}/firmware/compile")
    worker = threading.Thread(target=lambda: app_client.post(f"/api/projects/{first}/firmware/upload", json={"port": "FAKE0"})); worker.start()
    assert wait_for(lambda: "FAKE0" in app_client.app.state.hardware_uploading_ports)
    assert app_client.post(f"/api/projects/{second}/serial/start", json={"port": "FAKE0"}).json()["detail"]["code"] == "PORT_BUSY"
    assert app_client.post(f"/api/projects/{second}/firmware/upload", json={"port": "FAKE0"}).json()["detail"]["code"] == "PORT_BUSY"
    release.set(); worker.join()
    assert app_client.app.state.hardware_uploading_ports == {}


def test_an_edited_sketch_reports_its_own_revision_so_old_code_gives_no_evidence(app_client, monkeypatch):
    pid = project(app_client)
    firmware = app_client.get(f"/api/projects/{pid}/firmware").json()
    block = firmware["controlBlock"].replace("return prevOn;", "return prevOn;  // edited")
    assert app_client.put(f"/api/projects/{pid}/firmware/edit", json={"block": block, "revisionId": firmware["revisionId"]}).status_code == 200
    edited = app_client.get(f"/api/projects/{pid}/firmware").json()
    assert edited["boardRevision"].startswith(firmware["revisionId"] + "+edit-") and f'REVISION_ID = "{edited["boardRevision"]}"' in edited["source"]
    old = b"".join(json.dumps({"rev": firmware["revisionId"], "t_c": 20, "fan": 0}).encode() + b"\n" for _ in range(4))
    monkeypatch.setattr("aura.workspace.server.find_cli", lambda: "arduino-cli")
    monkeypatch.setattr("aura.hardware.serial.subprocess.Popen", lambda args, **kw: FakeProcess(old))
    app_client.post(f"/api/projects/{pid}/serial/start", json={"port": "COM7"})
    assert wait_for(lambda: app_client.get(f"/api/projects/{pid}/serial?after=0").json()["wrongRevision"] is not None)
    assert app_client.get(f"/api/projects/{pid}/serial?after=0").json()["evidence"] is None


def test_deep_json_and_reader_errors_never_kill_the_session_silently():
    assert parse_line(b'{"a":' + b"[" * 1990)["telemetry"] is None

    def broken(stop):
        yield "first"
        raise RuntimeError("serial driver glitch")
    session = SerialSession("FAKE0", "r", fake_source=broken); session.start()
    assert wait_for(lambda: not session.running)
    assert [line["text"] for line in session.lines(0)] == ["first", "Monitor reader stopped: RuntimeError"]


def test_monitor_runs_in_its_own_process_group_and_stop_kills_the_tree(monkeypatch):
    seen, killed = {}, []
    def popen(args, **kw):
        seen.update(kw); return FakeProcess(b"")
    monkeypatch.setattr(serial_module, "_kill_tree", lambda process: killed.append(process))
    session = SerialSession("COM7", "r", cli="arduino-cli", popen=popen)
    session._process = None; session.start()
    if os.name == "nt": assert seen["creationflags"] & __import__("subprocess").CREATE_NEW_PROCESS_GROUP
    else: assert seen["start_new_session"] is True
    session._process.killed = False
    session.stop()
    assert killed and all(process is session._process for process in killed)
