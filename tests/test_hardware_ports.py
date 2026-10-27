import json
import subprocess

from fastapi.testclient import TestClient

from aura.hardware.ports import list_ports
from aura.workspace.server import create_app

BOARD_LIST = {"detected_ports": [
    {"port": {"address": "COM1", "label": "COM1", "protocol": "serial", "properties": {}}},
    {"port": {"address": "COM5", "label": "COM5", "protocol": "serial", "properties": {"vid": "0x10C4", "pid": "0xEA60"}}},
]}


def runner(payload):
    return lambda command, timeout: subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


def test_lists_ports_and_tags_likely_esp32(monkeypatch):
    monkeypatch.delenv("AURA_FAKE_BOARD", raising=False)
    result = list_ports(cli="arduino-cli", run=runner(BOARD_LIST))
    assert result["toolchainMissing"] is None
    assert [(p["address"], p["likelyEsp32"], p["vid"], p["fake"]) for p in result["ports"]] == [("COM1", False, None, False), ("COM5", True, "10C4", False)]


def test_missing_toolchain_is_reported(monkeypatch):
    monkeypatch.delenv("AURA_FAKE_BOARD", raising=False)
    monkeypatch.setattr("aura.hardware.ports.find_cli", lambda: None)
    assert list_ports() == {"ports": [], "toolchainMissing": "arduino-cli"}


def test_fake_board_only_when_enabled(monkeypatch):
    monkeypatch.setenv("AURA_FAKE_BOARD", "1")
    ports = list_ports(cli="arduino-cli", run=runner({"detected_ports": []}))["ports"]
    assert ports == [{"address": "FAKE0", "label": "Fake board (test)", "protocol": "serial", "vid": None, "pid": None, "likelyEsp32": False, "fake": True}]


def test_ports_route(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_FAKE_BOARD", "1")
    monkeypatch.setattr("aura.hardware.ports.find_cli", lambda: None)
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        body = client.get("/api/hardware/ports").json()
    assert body["toolchainMissing"] == "arduino-cli" and [p["address"] for p in body["ports"]] == ["FAKE0"]
