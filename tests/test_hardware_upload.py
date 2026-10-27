import subprocess
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from aura.firmware.compile import CompileResult
from aura.firmware.sketch import FirmwareArtifact
from aura.hardware.upload import upload_hint, upload_sketch
from aura.workspace.server import create_app

ARTIFACT = FirmwareArtifact("void setup(){}\nvoid loop(){}\n", "revision-1", "esp32:esp32:esp32", (), {})


def test_upload_command_and_success():
    seen = []
    def run(command, timeout):
        seen.append(command); return subprocess.CompletedProcess(command, 0, "Hash of data verified.", "")
    result = upload_sketch(ARTIFACT, "COM5", cli="arduino-cli", run=run)
    assert seen[0][:7] == ["arduino-cli", "compile", "--upload", "-p", "COM5", "--fqbn", "esp32:esp32:esp32"]
    assert result.status == "uploaded" and result.port == "COM5" and result.revision_id == "revision-1" and result.fake is False


def test_upload_failure_keeps_tail_and_boot_hint():
    noise = "x" * 5000 + "\nA fatal error occurred: Failed to connect to ESP32: No serial data received."
    result = upload_sketch(ARTIFACT, "COM5", cli="arduino-cli", run=lambda c, timeout: subprocess.CompletedProcess(c, 2, "", noise))
    assert result.status == "failed" and len(result.raw_output) <= 2000 and result.hint == "Hold BOOT on the board while uploading."
    assert upload_hint("Access is denied") == "The port is in use or not permitted; close other serial programs."


def test_missing_cli_is_toolchain_missing(monkeypatch):
    monkeypatch.setattr("aura.hardware.upload.find_cli", lambda: None)
    assert upload_sketch(ARTIFACT, "COM5").status == "toolchain_missing"


@pytest.fixture()
def fan(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_FAKE_BOARD", "1")
    passed = lambda artifact, **kw: CompileResult("passed", (), 1000, artifact.revision_id, datetime.now(timezone.utc).isoformat(), "")
    monkeypatch.setattr("aura.workspace.server.compile_sketch", passed)
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project_id = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()["projectId"]
        yield client, project_id


def upload(client, project_id, port="FAKE0"):
    return client.post(f"/api/projects/{project_id}/firmware/upload", json={"port": port})


def test_upload_requires_a_passing_compile_of_the_current_revision(fan):
    client, project_id = fan
    assert upload(client, project_id).json()["detail"]["code"] == "COMPILE_REQUIRED"
    assert client.post(f"/api/projects/{project_id}/firmware/compile").json()["status"] == "passed"
    proposal = client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": 1, "componentDefinitionIds": ["led-generic"]}).json()
    client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit")
    response = upload(client, project_id)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "COMPILE_REQUIRED"


def test_fake_board_upload_and_busy_port(fan):
    client, project_id = fan
    client.post(f"/api/projects/{project_id}/firmware/compile")
    body = upload(client, project_id).json()
    assert body["status"] == "uploaded" and body["fake"] is True and body["port"] == "FAKE0"
    client.post(f"/api/projects/{project_id}/serial/start", json={"port": "FAKE0"})
    assert upload(client, project_id).json()["detail"]["code"] == "PORT_BUSY"
    assert upload(client, project_id, "-p evil").status_code == 422
    client.post(f"/api/projects/{project_id}/serial/stop")
