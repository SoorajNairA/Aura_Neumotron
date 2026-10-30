import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.electrical import materialize_electrical_nets
from aura.engineering_graph.model import EntityKind
from aura.engineering_graph.patches import apply_patch
from aura.verification.results import VerificationState
from aura.verification.service import VerificationService
from aura.workspace.edits import propose_wire
from aura.workspace.modifications import propose_add_components
from aura.workspace.server import create_app

OBJECTIVES = {"fan": "Build a temperature-controlled desk fan",
              "plant": "Build an automatic plant watering system with a soil moisture sensor and a pump"}
CODES = ("ELEC_DRIVER_CONFLICT", "ELEC_SUPPLY_RANGE", "ELEC_GROUND_MIX", "ELEC_LOGIC_LEVEL", "ELEC_I2C_ADDRESS", "ELEC_3V3_BUDGET", "ELEC_UNWIRED")
BOARD = "component-controller"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as c:
        yield c


def stored(client, name="fan"):
    """The demo project's graph exactly as stored (no read-time pin filling)."""
    pid = client.post("/api/projects", json={"objective": OBJECTIVES[name], "planningMode": "deterministic_test"}).json()["projectId"]
    return client.app.state.workspace.repository.get_project(pid).graph


def apply(graph, proposal):
    """Commit-equivalent: apply the patch and re-derive nets."""
    return materialize_electrical_nets(apply_patch(graph, proposal.patch))


def add(graph, *ids):
    proposal = propose_add_components(graph, len(graph.revisions), list(ids))
    return apply(graph, proposal), [op["targetId"] for op in proposal.operations if op["operation"] == "add_component"]


def edit(graph, action, **kwargs):
    return apply(graph, propose_wire(graph, len(graph.revisions), action, **kwargs))


def wire(graph, part, pin):
    """Id of the wire touching `part`'s `pin`."""
    return next(e.id for e in graph.find(kind=EntityKind.CONNECTION) for m in [e.metadata]
                if (m.get("source_id"), m.get("source_interface")) == (part, pin) or (m.get("target_id"), m.get("target_interface")) == (part, pin))


def findings(graph, code):
    return [f for f in VerificationService().verify_graph(graph).findings if f.check == code]


def failed(graph, code):
    return [f for f in findings(graph, code) if f.state is VerificationState.FAILED and f.blocking]


@pytest.mark.parametrize("name", ["fan", "plant"])
def test_fan_and_plant_demos_have_no_new_failures(client, name):
    result = VerificationService().verify_graph(stored(client, name))
    assert [f.check for f in result.findings if f.check in CODES and f.state is VerificationState.FAILED] == []
    assert result.accepted


def test_driver_conflict(client):
    graph, (sensor,) = add(stored(client), "ds18b20-module")
    assert not findings(graph, "ELEC_DRIVER_CONFLICT")
    # A 5 V supply on the board's 5V pin feeds it (that pin is also VIN); a 12 V one fights it.
    graph, (usb, wall) = add(graph, "supply-usb-5v-1a", "supply-dc-12v-2a")
    fed = edit(graph, "connect", source=(usb, "power"), target=(BOARD, "power"))
    assert not findings(fed, "ELEC_DRIVER_CONFLICT")
    fought = edit(graph, "connect", source=(wall, "power"), target=(BOARD, "power"))
    (finding,) = failed(fought, "ELEC_DRIVER_CONFLICT")
    assert finding.category == "electrical" and "5V" in finding.message and "+" in finding.message
    # Two part outputs on one wire.
    graph, (button,) = add(graph, "push-button")
    graph = edit(graph, "connect", source=(sensor, "signal"), target=(button, "signal"))
    (finding,) = failed(graph, "ELEC_DRIVER_CONFLICT")
    assert "DAT" in finding.message and set(finding.entity_ids) == {sensor, button}


def test_demo_read_with_pins_filled_has_no_new_failures(client):
    """Old projects and ZIPs come back with every part's pins filled from its template (Task 2); demos must still pass."""
    from aura.engineering_graph.serialization import graph_from_dict
    for name in OBJECTIVES:
        pid = client.post("/api/projects", json={"objective": OBJECTIVES[name], "planningMode": "deterministic_test"}).json()["projectId"]
        result = VerificationService().verify_graph(graph_from_dict(client.get(f"/api/projects/{pid}/graph").json()))
        assert [f.message for f in result.findings if f.check in CODES and f.state is VerificationState.FAILED] == []


def test_supply_range(client):
    graph, (led,) = add(stored(client), "led-generic")
    assert not findings(graph, "ELEC_SUPPLY_RANGE")
    graph = edit(graph, "reconnect", connection_id=wire(graph, led, "power"), end="source", source=(BOARD, "power"))
    (finding,) = failed(graph, "ELEC_SUPPLY_RANGE")
    assert "V+" in finding.message and "5" in finding.message


def test_ground_mix(client):
    graph, (sensor,) = add(stored(client), "ds18b20-module")
    assert not findings(graph, "ELEC_GROUND_MIX")
    graph = edit(graph, "connect", source=(sensor, "signal"), target=(BOARD, "ground"))
    assert failed(graph, "ELEC_GROUND_MIX") and "DAT" in failed(graph, "ELEC_GROUND_MIX")[0].message


def test_lcd1602_on_5v_fails_logic_level(client):
    graph, (lcd,) = add(stored(client), "lcd1602-i2c")
    found = failed(graph, "ELEC_LOGIC_LEVEL")
    assert found and found[0].message.endswith("Use a 3.3 V part or a level shifter.") and "SDA" in found[0].message


def test_logic_level_passes_for_3v3_parts_and_pir(client):
    graph, _ = add(stored(client), "ssd1306-oled-128x64", "pir-hc-sr501", "relay-module-5v")
    assert not findings(graph, "ELEC_LOGIC_LEVEL")


def test_i2c_address(client):
    graph, _ = add(stored(client), "ssd1306-oled-128x64", "bh1750-module")
    assert not findings(graph, "ELEC_I2C_ADDRESS")
    graph, (first, second) = add(stored(client), "bme280-i2c-module", "bme280-i2c-module")
    (finding,) = failed(graph, "ELEC_I2C_ADDRESS")
    assert set(finding.entity_ids) == {first, second} and "118" in finding.message
    # A configured address in parameters wins over the catalogue default.
    graph.entities[second].metadata["parameters"]["i2c_address"] = 119
    assert not findings(graph, "ELEC_I2C_ADDRESS")


def test_3v3_budget(client):
    graph = stored(client)
    assert not findings(graph, "ELEC_3V3_BUDGET")
    graph, _ = add(graph, "rfm95w-lora", "mfrc522-rfid", "nrf24l01-plus", "vl53l0x-module", "ssd1306-oled-128x64")
    assert not findings(graph, "ELEC_3V3_BUDGET")  # 120+100+14+20+20+1.5 mA
    graph, _ = add(graph, "dc-motor-6v")
    (finding,) = findings(graph, "ELEC_3V3_BUDGET")
    assert finding.severity == "warning" and not finding.blocking and finding.state is not VerificationState.FAILED


def test_unwired(client):
    graph, (led,) = add(stored(client), "led-generic")
    assert not findings(graph, "ELEC_UNWIRED")
    graph = edit(graph, "disconnect", connection_id=wire(graph, led, "signal"))
    (finding,) = findings(graph, "ELEC_UNWIRED")
    assert finding.message.endswith(": A is not wired — not electrically complete.")
    assert not finding.blocking and finding.severity == "warning"


def test_undo_of_reconnect_is_judged_on_restored_nets(client, monkeypatch):
    """Undo restores the edge by UPDATE_RELATIONSHIP; verification must re-derive nets for it."""
    results = []
    original = VerificationService.verify_modification
    monkeypatch.setattr(VerificationService, "verify_modification", lambda self, g, p: results.append(original(self, g, p)) or results[-1])
    pid = client.post("/api/projects", json={"objective": OBJECTIVES["fan"], "planningMode": "deterministic_test"}).json()["projectId"]
    proposal = client.post(f"/api/projects/{pid}/component-proposals", json={"baseRevision": 1, "componentDefinitionIds": ["led-generic"]}).json()
    assert client.post(f"/api/projects/{pid}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200
    led = next(op["targetId"] for op in proposal["operations"] if op["operation"] == "add_component")
    signal = next(c for c in proposal["operations"][0]["connectionIds"] if c.endswith("-signal"))
    # Move the LED end of its signal wire onto the driver: the LED's A pin is left unwired (a warning, so the commit goes through).
    moved = client.post(f"/api/projects/{pid}/wire-proposals", json={"baseRevision": 2, "action": "reconnect", "connectionId": signal, "end": "target",
                                                                       "targetId": "component-driver", "targetInterface": "signal"}).json()
    assert client.post(f"/api/projects/{pid}/modification-proposals/{moved['proposalId']}/commit").status_code == 200
    assert any(f.check == "ELEC_UNWIRED" and led in f.entity_ids for f in results[-1].findings)
    assert client.post(f"/api/projects/{pid}/revisions/undo", headers={"Idempotency-Key": "undo-1"}).status_code == 200
    assert results[-1].accepted and not any(f.check == "ELEC_UNWIRED" and led in f.entity_ids for f in results[-1].findings)
