import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.interfaces import ESP32_OUTPUT_GPIOS
from aura.engineering_graph.model import EngineeringGraph
from aura.workspace.modifications import ESP32_STRAPPING_GPIOS, ModificationError, propose_add_components
from aura.workspace.server import create_app

USED = (4, 16)  # fan demo: temperature_data, fan_gate
SAFE = [g for g in ESP32_OUTPUT_GPIOS if g not in ESP32_STRAPPING_GPIOS]
FREE_PORTS = 16 - len(USED)  # the board declares signal-1..signal-16; the bus ports (i2c/spi) are never handed out as plain GPIO


@pytest.fixture()
def fan(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()
        yield client, project["projectId"]


def add(client, project_id, ids, base=1):
    return client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": base, "componentDefinitionIds": ids})


def commit(client, project_id, proposal):
    return client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit")


def gpio_map(client, project_id):
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    controller = next(e for e in graph["entities"] if e["id"] == "component-controller")
    return controller["metadata"]["parameters"]["gpio_map"]


def added_pins(proposal):
    return [op["gpio"] for op in proposal["operations"] if op["operation"] == "add_component" and op.get("gpio") is not None]


def test_adds_one_part_and_allocates_lowest_safe_free_pin(fan):
    client, project_id = fan
    response = add(client, project_id, ["ds18b20-module"])
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["mode"] == "add_component"
    assert added_pins(proposal) == [min(g for g in SAFE if g not in USED)]
    assert any(c["state"] == "WARNING" for c in proposal["verification"]["checks"])


def test_same_definition_twice_gets_distinct_ids_and_pins(fan):
    client, project_id = fan
    proposal = add(client, project_id, ["ds18b20-module", "ds18b20-module"]).json()
    ids = [op["targetId"] for op in proposal["operations"] if op["operation"] == "add_component"]
    pins = added_pins(proposal)
    assert len(set(ids)) == 2 and len(set(pins)) == 2
    assert not set(pins) & (set(USED) | set(ESP32_STRAPPING_GPIOS))


def test_allocation_respects_pin_change(fan):
    client, project_id = fan
    lowest = min(g for g in SAFE if g not in USED)
    pin = client.post(f"/api/projects/{project_id}/pin-proposals",
                      json={"baseRevision": 1, "controllerId": "component-controller", "port": "signal-2", "gpio": lowest}).json()
    assert commit(client, project_id, pin).status_code == 200
    proposal = add(client, project_id, ["ds18b20-module"], base=2).json()
    assert added_pins(proposal) != [lowest]
    assert added_pins(proposal)[0] not in gpio_map(client, project_id).values()


def test_passive_part_gets_no_pin(fan):
    client, project_id = fan
    proposal = add(client, project_id, ["resistor-4k7"]).json()
    assert added_pins(proposal) == []
    assert commit(client, project_id, proposal).status_code == 200
    assert set(gpio_map(client, project_id).values()) == set(USED)


def test_errors(fan):
    client, project_id = fan
    assert add(client, project_id, ["no-such-part"]).json()["detail"]["code"] == "UNKNOWN_COMPONENT"
    assert add(client, project_id, ["no-such-part"]).status_code == 404
    empty = add(client, project_id, [])
    assert empty.status_code == 422 and empty.json()["detail"]["code"] == "EMPTY_SELECTION"
    stale = add(client, project_id, ["ds18b20-module"], base=0)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_revision"
    full = add(client, project_id, ["ds18b20-module"] * (FREE_PORTS + 1))
    assert full.status_code == 409 and full.json()["detail"]["code"] == "NO_FREE_PIN"
    with pytest.raises(ModificationError) as error:
        propose_add_components(EngineeringGraph("project-empty"), 0, ["ds18b20-module"])
    assert error.value.code == "NO_CONTROLLER"


def test_route_commit_then_undo(fan):
    client, project_id = fan
    proposal = add(client, project_id, ["ds18b20-module"]).json()
    new_id = next(op["targetId"] for op in proposal["operations"] if op["operation"] == "add_component")
    assert commit(client, project_id, proposal).status_code == 200
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    assert new_id in {e["id"] for e in graph["entities"]}
    assert any(e["kind"] == "connection" and new_id in (e["metadata"].get("source_id"), e["metadata"].get("target_id")) for e in graph["entities"])
    assert new_id in {p["semanticId"] for p in client.get(f"/api/projects/{project_id}/assembly").json()["parts"]}
    undo = client.post(f"/api/projects/{project_id}/revisions/undo", headers={"Idempotency-Key": "undo-add"})
    assert undo.status_code == 200, undo.text
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    assert new_id not in {e["id"] for e in graph["entities"]}
    assert not any(e["kind"] == "connection" and new_id in (e["metadata"].get("source_id"), e["metadata"].get("target_id")) for e in graph["entities"])
    assert set(gpio_map(client, project_id).values()) == set(USED)


def test_fan_firmware_still_supported_after_add(fan):
    client, project_id = fan
    before = client.get(f"/api/projects/{project_id}/firmware").json()
    assert commit(client, project_id, add(client, project_id, ["ds18b20-module"]).json()).status_code == 200
    after = client.get(f"/api/projects/{project_id}/firmware").json()
    assert after["supported"] is True, after["reasons"]
    assert after["pins"] == before["pins"]
    assert after["source"].replace(after["revisionId"], "R") == before["source"].replace(before["revisionId"], "R")


def test_firmware_lists_added_parts_without_driver(fan):
    client, project_id = fan
    assert client.get(f"/api/projects/{project_id}/firmware").json()["addedWithoutDriver"] == []
    proposal = add(client, project_id, ["ds18b20-module", "resistor-4k7"]).json()
    assert commit(client, project_id, proposal).status_code == 200
    added = next(op for op in proposal["operations"] if op["operation"] == "add_component" and op["gpio"] is not None)
    assert client.get(f"/api/projects/{project_id}/firmware").json()["addedWithoutDriver"] == [
        {"semanticId": added["targetId"], "name": added["newValue"], "port": added["port"], "gpio": added["gpio"]}]


def test_adds_stay_within_declared_controller_ports_and_later_edits_still_verify(fan):
    client, project_id = fan
    # The ESP32 declares signal-1..signal-16; the fan uses two, so fourteen more fit.
    too_many = add(client, project_id, ["ds18b20-module"] * (FREE_PORTS + 1))
    assert too_many.status_code == 409 and too_many.json()["detail"]["code"] == "NO_FREE_PIN"
    assert commit(client, project_id, add(client, project_id, ["ds18b20-module"] * FREE_PORTS).json()).status_code == 200
    edit = client.post(f"/api/projects/{project_id}/parameter-proposals",
                       json={"baseRevision": 2, "componentId": "component-temperature-sensor", "key": "threshold_c", "value": 30.0}).json()
    assert client.post(f"/api/projects/{project_id}/modification-proposals/{edit['proposalId']}/commit").status_code == 200


def test_every_add_warns_power_and_ground_are_unwired_and_switch_is_an_input(fan):
    client, project_id = fan
    relay = add(client, project_id, ["relay-module-5v"]).json()
    assert any(c["state"] == "WARNING" and "Power and ground" in c["message"] for c in relay["verification"]["checks"])
    switch_id = next(d for d in __import__("aura.verification.catalogue", fromlist=["BY_ID"]).BY_ID.values() if d.family == "switch").component_definition_id
    proposal = add(client, project_id, [switch_id]).json()
    assert commit(client, project_id, proposal).status_code == 200
    part = next(op["targetId"] for op in proposal["operations"] if op["operation"] == "add_component")
    wire = next(e for e in client.get(f"/api/projects/{project_id}/graph").json()["entities"] if e["kind"] == "connection" and part in (e["metadata"].get("source_id"), e["metadata"].get("target_id")))
    assert wire["metadata"]["source_id"] == part and wire["metadata"]["connection_type"] == "signal"
