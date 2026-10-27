import io
import json
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from aura.firmware.compile import CompileResult
from aura.hardware.serial import SerialSession, evidence, parse_line
from aura.workspace.server import create_app


def test_parse_line_handles_json_raw_bad_bytes_and_huge_lines():
    assert parse_line(b'{"rev":"r1","soil_1":40.5,"pump_1":0}\r\n') == {"text": '{"rev":"r1","soil_1":40.5,"pump_1":0}', "telemetry": {"rev": "r1", "soil_1": 40.5, "pump_1": 0}}
    assert parse_line(b"ets Jun  8 2016 rst:0x1\n")["telemetry"] is None
    assert parse_line(b"\xff\xfe{bad")["telemetry"] is None and "�" in parse_line(b"\xff\xfe{bad")["text"]
    assert parse_line(b'{"no_rev":1}')["telemetry"] is None and parse_line(b"[1,2]")["telemetry"] is None
    assert len(parse_line(b"x" * 10000)["text"]) == 2000


class FakeProcess:
    def __init__(self, data):
        self.stdout, self.killed, self.args = io.BytesIO(data), False, None
    def poll(self): return 0 if self.killed else None
    def terminate(self): self.killed = True
    def kill(self): self.killed = True
    def wait(self, timeout=None): return 0


def wait_for(predicate, seconds=3):
    end = time.time() + seconds
    while time.time() < end:
        if predicate(): return True
        time.sleep(.02)
    return False


def test_session_buffers_lines_and_stop_kills_the_process():
    procs = []
    def popen(args, **kw):
        procs.append(FakeProcess(b"boot\n" + b'{"rev":"r1","t_c":21.0,"fan":0}\n' * 3)); procs[-1].args = args; return procs[-1]
    session = SerialSession("COM5", "r1", cli="arduino-cli", popen=popen)
    session.start()
    assert wait_for(lambda: len(session.lines(0)) == 4)
    assert procs[0].args == ["arduino-cli", "monitor", "-p", "COM5", "-q", "--config", "115200"]
    assert [line["seq"] for line in session.lines(2)] == [3, 4]
    session.stop()
    assert procs[0].killed and not session.running


def test_evidence_needs_three_current_non_fake_lines():
    lines = [{"seq": i, "time": "t", "text": "", "telemetry": {"rev": "r1"}} for i in range(1, 4)]
    found = evidence(lines, "r1", port="COM5", fake=False)
    assert found["revisionId"] == "r1" and found["lines"] == 3 and found["port"] == "COM5" and found["agreement"] == "not checked"
    assert evidence(lines[:2], "r1", port="COM5", fake=False) is None
    assert evidence(lines, "r2", port="COM5", fake=False) is None
    assert evidence(lines, "r1", port="FAKE0", fake=True) is None


@pytest.fixture()
def fan(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_FAKE_BOARD", "1")
    monkeypatch.setattr("aura.workspace.server.compile_sketch", lambda a, **kw: CompileResult("passed", (), 1, a.revision_id, datetime.now(timezone.utc).isoformat(), ""))
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project_id = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()["projectId"]
        yield client, project_id
        client.post(f"/api/projects/{project_id}/serial/stop")


def test_fake_board_monitor_streams_telemetry_without_evidence(fan):
    client, project_id = fan
    assert client.post(f"/api/projects/{project_id}/serial/start", json={"port": "FAKE0"}).status_code == 200
    assert wait_for(lambda: sum(1 for l in client.get(f"/api/projects/{project_id}/serial?after=0").json()["lines"] if l["telemetry"]) >= 1, 4)
    body = client.get(f"/api/projects/{project_id}/serial?after=0").json()
    assert body["running"] and body["fake"] and body["port"] == "FAKE0" and body["evidence"] is None and body["wrongRevision"] is None
    telemetry = next(l["telemetry"] for l in body["lines"] if l["telemetry"])
    assert {"rev", "t_c", "fan"} <= set(telemetry)
    client.post(f"/api/projects/{project_id}/firmware/compile")
    upload = client.post(f"/api/projects/{project_id}/firmware/upload", json={"port": "FAKE0"})
    assert upload.status_code == 409 and upload.json()["detail"]["code"] == "PORT_BUSY"
    client.post(f"/api/projects/{project_id}/serial/stop")
    assert client.get(f"/api/projects/{project_id}/serial?after=0").json()["running"] is False
    assert client.get(f"/api/projects/{project_id}/firmware").json()["hardwareEvidence"] is None


def test_real_port_telemetry_writes_evidence_and_flags_wrong_revision(fan, monkeypatch):
    client, project_id = fan
    current = client.get(f"/api/projects/{project_id}/firmware").json()["revisionId"]
    lines = b"".join(json.dumps({"rev": current, "t_c": 20, "fan": 0}).encode() + b"\n" for _ in range(3))
    monkeypatch.setattr("aura.workspace.server.find_cli", lambda: "arduino-cli")
    monkeypatch.setattr("aura.hardware.serial.subprocess.Popen", lambda args, **kw: FakeProcess(lines))
    assert client.post(f"/api/projects/{project_id}/serial/start", json={"port": "COM5"}).status_code == 200
    assert wait_for(lambda: client.get(f"/api/projects/{project_id}/serial?after=0").json()["evidence"] is not None)
    stored = client.get(f"/api/projects/{project_id}/firmware").json()["hardwareEvidence"]
    assert stored["port"] == "COM5" and stored["revisionId"] == current and stored["lines"] >= 3
    client.post(f"/api/projects/{project_id}/serial/stop")
    monkeypatch.setattr("aura.hardware.serial.subprocess.Popen", lambda args, **kw: FakeProcess(b'{"rev":"old","t_c":20,"fan":0}\n'))
    client.post(f"/api/projects/{project_id}/serial/start", json={"port": "COM5"})
    assert wait_for(lambda: client.get(f"/api/projects/{project_id}/serial?after=0").json()["wrongRevision"] == {"board": "old", "current": current})


def test_second_start_replaces_the_first_session(fan):
    client, project_id = fan
    client.post(f"/api/projects/{project_id}/serial/start", json={"port": "FAKE0"})
    first = client.app.state.serial_sessions[project_id]
    client.post(f"/api/projects/{project_id}/serial/start", json={"port": "FAKE0"})
    assert not first.running and client.app.state.serial_sessions[project_id] is not first


def test_app_shutdown_stops_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_FAKE_BOARD", "1")
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project_id = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()["projectId"]
        client.post(f"/api/projects/{project_id}/serial/start", json={"port": "FAKE0"})
        session = client.app.state.serial_sessions[project_id]
        assert session.running
    assert not session.running and client.app.state.hardware_busy_ports == {}
