import json

import pytest
from fastapi.testclient import TestClient

from aura.workspace.server import create_app

OBJECTIVE = "Build a temperature-controlled desk fan"
CONTROLLER = "component-controller"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as c:
        yield c


def graph(client, pid):
    return client.get(f"/api/projects/{pid}/graph").json()


def settled(g):
    """graph_to_dict minus revisions and the evidence/verification records, which a commit marks stale (by design, until re-verified)."""
    return {k: ([e for e in v if e["kind"] not in ("evidence", "verification_result")] if k == "entities" else v) for k, v in g.items() if k != "revisions"}


def commit(client, pid, proposal):
    return client.post(f"/api/projects/{pid}/modification-proposals/{proposal['proposalId']}/commit")


def wire_edit(client, pid, **body):
    body.setdefault("baseRevision", len(graph(client, pid)["revisions"]))
    return client.post(f"/api/projects/{pid}/wire-proposals", json=body)


def wire(g, connection_id):
    entity = next((e for e in g["entities"] if e["id"] == connection_id), None)
    edge = next((r for r in g["relationships"] if r["id"] == f"{connection_id}-edge"), None)
    return entity, edge


def wires_between(g, a, b, interface):
    return [e for e in g["entities"] if e["kind"] == "connection" and {e["metadata"].get("source_id"), e["metadata"].get("target_id")} == {a, b}
            and interface in (e["metadata"]["source_interface"], e["metadata"]["target_interface"])]


@pytest.fixture()
def led(client):
    """A fan project with a catalogue LED added and auto-wired; returns (project id, led id, id of its signal wire)."""
    pid = client.post("/api/projects", json={"objective": OBJECTIVE, "planningMode": "deterministic_test"}).json()["projectId"]
    proposal = client.post(f"/api/projects/{pid}/component-proposals", json={"baseRevision": 1, "componentDefinitionIds": ["led-generic"]}).json()
    assert commit(client, pid, proposal).status_code == 200
    led_id = next(op["targetId"] for op in proposal["operations"] if op["operation"] == "add_component")
    signal = next(c for c in proposal["operations"][0]["connectionIds"] if c.endswith("-signal"))
    return pid, led_id, signal


def test_connect_adds_wire_and_commits(client, led):
    pid, led_id, signal = led
    assert commit(client, pid, wire_edit(client, pid, action="disconnect", connectionId=signal).json()).status_code == 200
    response = wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="signal", targetId=CONTROLLER, targetInterface="signal-5")
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["mode"] == "connect" and proposal["operations"][0]["operation"] == "snapshot_edit"
    assert commit(client, pid, proposal).status_code == 200
    g = graph(client, pid)
    found = wires_between(g, led_id, CONTROLLER, "signal-5")
    assert len(found) == 1
    entity, edge = wire(g, found[0]["id"])
    assert (edge["source_id"], edge["target_id"], edge["type"]) == (entity["metadata"]["source_id"], entity["metadata"]["target_id"], entity["metadata"]["connection_type"])
    # The board drives the LED, so it is a control wire from the board's pin, whichever order the pins were sent in.
    assert entity["metadata"]["connection_type"] == "control" and entity["metadata"]["source_id"] == CONTROLLER
    assert any(e["metadata"].get("semantic_type") == "electrical_net" and {"componentId": CONTROLLER, "interfaceId": "signal-5"} in e["metadata"]["terminals"]
               for e in g["entities"])


def test_connection_type_comes_from_pin_roles(client, led):
    pid, led_id, signal = led
    for kind in ("power", "ground"):
        proposal = wire_edit(client, pid, action="disconnect", connectionId=signal.replace("-signal", f"-{kind}")).json()
        assert commit(client, pid, proposal).status_code == 200
    power = wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="power", targetId=CONTROLLER, targetInterface="vcc-out").json()
    assert commit(client, pid, power).status_code == 200
    ground = wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="ground", targetId=CONTROLLER, targetInterface="ground").json()
    assert commit(client, pid, ground).status_code == 200
    types = {(m["source_id"], m["source_interface"], m["target_id"], m["target_interface"]): m["connection_type"]
             for e in graph(client, pid)["entities"] if e["kind"] == "connection" for m in [e["metadata"]] if "source_id" in m}
    assert types[(CONTROLLER, "vcc-out", led_id, "power")] == "power"  # the power_out end is the source whichever order was sent
    assert types[(CONTROLLER, "ground", led_id, "ground")] == "ground"


def test_reconnect_moves_one_end_keeps_id(client, led):
    pid, led_id, signal = led
    old_port = wire(graph(client, pid), signal)[0]["metadata"]["source_interface"]
    new_port = "signal-9" if old_port != "signal-9" else "signal-10"
    response = wire_edit(client, pid, action="reconnect", connectionId=signal, end="source", sourceId=CONTROLLER, sourceInterface=new_port)
    assert response.status_code == 200
    assert commit(client, pid, response.json()).status_code == 200
    g = graph(client, pid)
    entity, edge = wire(g, signal)
    assert entity["metadata"]["source_interface"] == new_port and entity["metadata"]["source_id"] == CONTROLLER
    assert (entity["metadata"]["target_id"], entity["metadata"]["target_interface"]) == (led_id, "signal")
    assert (edge["source_id"], edge["target_id"]) == (CONTROLLER, led_id)
    assert sum(1 for e in g["entities"] if e["id"] == signal) == 1
    # Moving the target end to another part rewrites the edge endpoints too.
    moved = wire_edit(client, pid, action="reconnect", connectionId=signal, end="target", targetId="component-driver", targetInterface="signal").json()
    assert commit(client, pid, moved).status_code == 200
    entity, edge = wire(graph(client, pid), signal)
    assert (entity["metadata"]["target_id"], edge["target_id"]) == ("component-driver", "component-driver") and edge["source_id"] == CONTROLLER


@pytest.mark.xfail(strict=True, reason="Task 6")
def test_disconnect_removes_wire_and_warns_unwired(client, led):
    pid, led_id, signal = led
    proposal = wire_edit(client, pid, action="disconnect", connectionId=signal).json()
    assert proposal["mode"] == "disconnect"
    assert commit(client, pid, proposal).status_code == 200
    assert wire(graph(client, pid), signal) == (None, None)
    assert "ELEC_UNWIRED" in json.dumps(client.get(f"/api/projects/{pid}/verification").json())


def test_each_wire_edit_undoes_to_equal_graph(client, led):
    pid, led_id, signal = led
    port = wire(graph(client, pid), signal)[0]["metadata"]["source_interface"]
    free = "signal-9" if port != "signal-9" else "signal-10"
    undo_n = 0
    def undo():
        nonlocal undo_n; undo_n += 1
        assert client.post(f"/api/projects/{pid}/revisions/undo", headers={"Idempotency-Key": f"undo-{undo_n}"}).status_code == 200
    for body in (dict(action="reconnect", connectionId=signal, end="source", sourceId=CONTROLLER, sourceInterface=free), dict(action="disconnect", connectionId=signal)):
        before = settled(graph(client, pid))
        assert commit(client, pid, wire_edit(client, pid, **body).json()).status_code == 200
        assert settled(graph(client, pid)) != before
        undo()
        assert settled(graph(client, pid)) == before
    assert commit(client, pid, wire_edit(client, pid, action="disconnect", connectionId=signal).json()).status_code == 200
    before = settled(graph(client, pid))
    connect = wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="signal", targetId=CONTROLLER, targetInterface="signal-5").json()
    assert commit(client, pid, connect).status_code == 200
    undo()
    assert settled(graph(client, pid)) == before


def test_unknown_pin_and_duplicate_wire(client, led):
    pid, led_id, signal = led
    def code(response): return response.status_code, response.json()["detail"]["code"]
    assert code(wire_edit(client, pid, action="connect", sourceId="component-nope", sourceInterface="signal", targetId=CONTROLLER, targetInterface="signal-5")) == (404, "UNKNOWN_PIN")
    assert code(wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="nope", targetId=CONTROLLER, targetInterface="signal-5")) == (422, "UNKNOWN_PIN")
    assert code(wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="signal", targetId=CONTROLLER, targetInterface="signal-99")) == (422, "UNKNOWN_PIN")
    assert code(wire_edit(client, pid, action="reconnect", connectionId=signal, end="source", sourceId=CONTROLLER, sourceInterface="nope")) == (422, "UNKNOWN_PIN")
    m = wire(graph(client, pid), signal)[0]["metadata"]
    for ends in ((m["source_id"], m["source_interface"], m["target_id"], m["target_interface"]), (m["target_id"], m["target_interface"], m["source_id"], m["source_interface"])):
        assert code(wire_edit(client, pid, action="connect", sourceId=ends[0], sourceInterface=ends[1], targetId=ends[2], targetInterface=ends[3])) == (409, "WIRE_EXISTS")
    other = wire_edit(client, pid, action="connect", sourceId=led_id, sourceInterface="signal", targetId=CONTROLLER, targetInterface="signal-12" if m["source_interface"] != "signal-12" else "signal-11").json()
    assert commit(client, pid, other).status_code == 200
    other_id = next(e["id"] for e in graph(client, pid)["entities"] if e["kind"] == "connection" and e["metadata"].get("source_id") == CONTROLLER
                    and e["metadata"].get("target_id") == led_id and e["id"] != signal and e["metadata"]["source_interface"].startswith("signal-"))
    assert code(wire_edit(client, pid, action="reconnect", connectionId=other_id, end="source", sourceId=CONTROLLER, sourceInterface=m["source_interface"])) == (409, "WIRE_EXISTS")
    assert code(wire_edit(client, pid, action="disconnect", connectionId="connection-nope")) == (404, "UNKNOWN_WIRE")
    assert code(wire_edit(client, pid, action="disconnect", connectionId="connection-support-controller-mechanical")) == (422, "NOT_A_WIRE")


def test_stale_base_409(client, led):
    pid, led_id, signal = led
    response = wire_edit(client, pid, action="disconnect", connectionId=signal, baseRevision=1)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "stale_revision"
