import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind, Relationship
from aura.workspace.modifications import inverse_proposal, propose_add_components
from aura.workspace.server import create_app

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "demo_wires.json").read_text(encoding="utf-8"))
OBJECTIVES = {"fan": "Build a temperature-controlled desk fan",
              "plant": "Build an automatic plant watering system with a soil moisture sensor and a pump"}


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as c:
        yield c


def project(client, objective="fan"):
    return client.post("/api/projects", json={"objective": OBJECTIVES[objective], "planningMode": "deterministic_test"}).json()["projectId"]


def graph(client, project_id):
    return client.get(f"/api/projects/{project_id}/graph").json()


def add(client, project_id, ids, base=1):
    return client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": base, "componentDefinitionIds": ids})


def commit(client, project_id, proposal):
    return client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit")


def wires(client, project_id, part):
    """{part pin: (other end pin, connection type, other end id, part is the source)} for every wire touching `part`."""
    result = {}
    for e in graph(client, project_id)["entities"]:
        m = e["metadata"]
        if e["kind"] != "connection" or "source_id" not in m or part not in (m["source_id"], m["target_id"]): continue
        mine, theirs = ("source", "target") if m["source_id"] == part else ("target", "source")
        result[m[f"{mine}_interface"]] = (m[f"{theirs}_interface"], m["connection_type"], m[f"{theirs}_id"], m["source_id"] == part)
    return result


def part_id(proposal, index=0):
    return [op["targetId"] for op in proposal["operations"] if op["operation"] == "add_component"][index]


def gpio_map(client, project_id):
    controller = next(e for e in graph(client, project_id)["entities"] if e["id"] == "component-controller")
    return controller["metadata"]["parameters"]["gpio_map"]


def settled(g):
    """graph_to_dict minus revisions and the evidence/verification records, which an add marks stale on the parts it touches (by design, until re-verified)."""
    return {k: ([e for e in v if e["kind"] not in ("evidence", "verification_result")] if k == "entities" else v) for k, v in g.items() if k != "revisions"}


def demo_wires(client, name):
    project_id = project(client, name); g = graph(client, project_id)
    connections = sorted([m["source_id"], m["source_interface"], m["target_id"], m["target_interface"], m["connection_type"]]
                         for e in g["entities"] if e["kind"] == "connection" for m in [e["metadata"]] if "source_id" in m)
    maps = {e["id"]: e["metadata"]["parameters"]["gpio_map"] for e in g["entities"]
            if e["kind"] == "component" and e["metadata"].get("parameters", {}).get("gpio_map") is not None}
    return {"wires": connections, "gpio_maps": maps}


@pytest.mark.parametrize("name", ["fan", "plant"])
def test_fan_and_plant_migration_unchanged(client, name):
    assert demo_wires(client, name) == FIXTURE[name]


def test_add_ds18b20_gets_power_ground_and_signal(client):
    project_id = project(client)
    proposal = add(client, project_id, ["ds18b20-module"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    found = wires(client, project_id, part_id(proposal))
    assert set(found) == {"power", "ground", "signal"}
    assert found["power"] == ("vcc-out", "power", "component-controller", False)  # 3.0-5.5 V includes 3.3 V
    assert found["ground"][:3] == ("ground", "ground", "component-controller")
    assert found["signal"][1:] == ("signal", "component-controller", True) and found["signal"][0].startswith("signal-")
    assert found["signal"][0] in gpio_map(client, project_id)
    assert not any(c["state"] == "WARNING" and "Power and ground" in c["message"] for c in proposal["verification"]["checks"])


def test_five_volt_part_uses_the_5v_pin(client):
    project_id = project(client)
    proposal = add(client, project_id, ["relay-module-5v"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    found = wires(client, project_id, part_id(proposal))
    assert found["power"][:2] == ("power", "power") and found["signal"][1] == "control" and found["signal"][3] is False


def test_hc_sr04_gets_two_signal_ports_by_its_own_pin_names(client):
    project_id = project(client)
    proposal = add(client, project_id, ["hc-sr04-class"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    found = wires(client, project_id, part_id(proposal))
    assert set(found) == {"power", "ground", "trig", "echo"}
    assert found["trig"][1] == "control" and found["echo"][1] == "signal"
    assert found["trig"][0] != found["echo"][0] and "signal" not in found


def test_two_i2c_parts_share_bus_ports(client):
    project_id = project(client)
    proposal = add(client, project_id, ["ssd1306-oled-128x64", "bh1750-module"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    for index in (0, 1):
        found = wires(client, project_id, part_id(proposal, index))
        assert found["sda"][0] == "i2c-sda" and found["scl"][0] == "i2c-scl" and found["sda"][2] == "component-controller"
    assert {k: gpio_map(client, project_id)[k] for k in ("i2c-sda", "i2c-scl")} == {"i2c-sda": 21, "i2c-scl": 22}
    again = add(client, project_id, ["mpu6050-module"], base=2).json()
    assert commit(client, project_id, again).status_code == 200
    assert wires(client, project_id, part_id(again))["sda"][0] == "i2c-sda"


def test_spi_part_gets_own_cs(client):
    project_id = project(client)
    proposal = add(client, project_id, ["mfrc522-rfid", "max7219-matrix"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    first, second = (wires(client, project_id, part_id(proposal, i)) for i in (0, 1))
    assert first["sck"][0] == second["sck"][0] == "spi-sck" and first["mosi"][0] == second["mosi"][0] == "spi-mosi"
    assert first["miso"][0] == "spi-miso" and first["miso"][1] == "signal"
    assert first["cs"][0].startswith("signal-") and second["cs"][0].startswith("signal-") and first["cs"][0] != second["cs"][0]
    assert gpio_map(client, project_id)["spi-sck"] == 18


def test_bus_pins_in_use_names_holder(client):
    project_id = project(client)
    pin = client.post(f"/api/projects/{project_id}/pin-proposals",
                      json={"baseRevision": 1, "controllerId": "component-controller", "port": "signal-2", "gpio": 21}).json()
    assert commit(client, project_id, pin).status_code == 200
    response = add(client, project_id, ["ssd1306-oled-128x64"], base=2)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "BUS_PINS_IN_USE" and "signal-2" in detail["message"]


def test_second_uart_part_refused(client):
    project_id = project(client)
    proposal = add(client, project_id, ["neo6m-gps"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    wired = wires(client, project_id, part_id(proposal))
    assert {"tx", "rx"} <= set(wired) and wired["tx"][0] != wired["rx"][0]
    again = add(client, project_id, ["neo6m-gps"], base=2)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "UART_IN_USE"
    twice = add(client, project_id, ["neo6m-gps", "neo6m-gps"], base=2)
    assert twice.status_code == 409 and twice.json()["detail"]["code"] == "UART_IN_USE"


def test_12v_pump_needs_external_supply(client):
    project_id = project(client)
    response = add(client, project_id, ["micro-pump-12v"])
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "NEEDS_EXTERNAL_SUPPLY" and "9–12 V" in detail["message"] and "add a supply first" in detail["message"]


def test_undo_add_removes_all_wires(client):
    project_id = project(client)
    before = settled(graph(client, project_id))
    proposal = add(client, project_id, ["ds18b20-module", "ssd1306-oled-128x64"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    assert len(wires(client, project_id, part_id(proposal))) == 3
    assert client.post(f"/api/projects/{project_id}/revisions/undo", headers={"Idempotency-Key": "undo-autowire"}).status_code == 200
    assert settled(graph(client, project_id)) == before


def test_old_single_connection_id_add_undo_still_works():
    g = EngineeringGraph("project-x")
    g.entities["project-x"] = EngineeringEntity("project-x", EntityKind.PROJECT, "x", None, {})
    g.entities["component-user-a"] = EngineeringEntity("component-user-a", EntityKind.COMPONENT, "A", "project-x", {})
    g.entities["connection-user-wire-1"] = EngineeringEntity("connection-user-wire-1", EntityKind.CONNECTION, "w", "project-x", {})
    g.relationships["connection-user-wire-1-edge"] = Relationship("connection-user-wire-1-edge", "component-user-a", "project-x", "signal", {})
    class Patch: summary = "Add A"
    old = {"operation": "add_component", "targetId": "component-user-a", "newValue": "A", "connectionId": "connection-user-wire-1"}
    new = {"operation": "add_component", "targetId": "component-user-a", "newValue": "A", "connectionIds": ["connection-user-wire-1"]}
    for item in (old, new):
        removed = {op.target_id for op in inverse_proposal(g, {"patch": Patch, "verification": {"diff": {"changed": [item]}}}).patch.operations}
        assert {"connection-user-wire-1", "connection-user-wire-1-edge", "component-user-a"} <= removed


def test_add_without_controller_is_unwired_with_warning():
    proposal = propose_add_components(EngineeringGraph("project-empty"), 0, ["ds18b20-module"])
    assert [op.operation.value for op in proposal.patch.operations] == ["add_entity"]
    assert any(c["state"] == "WARNING" and "No supported controller" in c["message"] and "added unwired" in c["message"]
               for c in proposal.verification["checks"])
