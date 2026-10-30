import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.interfaces import BUS_GPIOS, allocate_gpio, component_interfaces
from aura.verification.catalogue import CATALOGUE
from aura.workspace.server import create_app

# Captured from component_interfaces("microcontroller_board", (28, 52, 12)) before the bus ports were added.
ORIGINAL_BOARD_PORTS = [
    ("power", "electrical_power_in", (-14.0, -26.0, 6.0)), ("ground", "electrical_ground", (-7.0, -26.0, 6.0)),
    ("signal-1", "control_output", (0.0, -26.0, 6.0)), ("signal-2", "control_output", (7.0, -26.0, 6.0)),
    *((f"signal-{n}", "control_output", (14.0, -26.0, 6.0)) for n in range(3, 9)), ("vcc-out", "electrical_power_out", (14.0, -26.0, 6.0)),
]
FAN = "Design a temperature-controlled desk fan"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        yield client


def test_existing_board_port_positions_unchanged():
    ports = component_interfaces("microcontroller_board", (28, 52, 12))
    assert [(i.name, i.kind, i.position) for i in ports[:11]] == ORIGINAL_BOARD_PORTS


def test_bus_ports_appended():
    ports = {i.name: i for i in component_interfaces("microcontroller_board", (28, 52, 12))}
    names = [i.name for i in component_interfaces("microcontroller_board", (28, 52, 12))]
    assert names.index("vcc-out") == 10 and all(names.index(n) > 10 for n in (*BUS_GPIOS, *(f"signal-{k}" for k in range(9, 17))))
    assert all(ports[n].kind == "control_output" for n in (*BUS_GPIOS, *(f"signal-{k}" for k in range(9, 17))))
    assert BUS_GPIOS == {"i2c-sda": 21, "i2c-scl": 22, "spi-sck": 18, "spi-mosi": 23, "spi-miso": 19}


def test_existing_family_ports_do_not_move():
    # Appended override ports (sda/scl...) must not change the pitch of the ports a family always had.
    assert [(i.name, i.position) for i in component_interfaces("temperature_sensor", (45, 20, 15))[:3]] == [
        ("power", (-22.5, -10.0, 7.5)), ("ground", (-7.5, -10.0, 7.5)), ("signal", (7.5, -10.0, 7.5))]


def test_every_catalogue_pin_name_is_a_family_interface():
    for d in CATALOGUE:
        names = {i.name for i in component_interfaces(d.family, tuple(d.properties["dimensions"].value) if "dimensions" in d.properties else (10, 10, 10))}
        assert {p.name for p in d.pins} <= names, (d.component_definition_id, {p.name for p in d.pins} - names)


def test_allocator_prefers_non_bus_pins():
    assert allocate_gpio("motion_sensor", None, {4, 13, 14, 16, 17}) not in BUS_GPIOS.values()
    # bus pins are still available as a last resort
    assert allocate_gpio("motion_sensor", None, {4, 13, 14, 16, 17, 25, 26, 27, 32, 33, 34, 35, 36, 37, 38, 39}) in BUS_GPIOS.values()


def test_graph_route_fills_pins_for_legacy_entities(client):
    project = client.post("/api/projects", json={"objective": FAN, "planningMode": "deterministic_test"}).json()
    graph = client.get(f"/api/projects/{project['projectId']}/graph").json()
    components = [e for e in graph["entities"] if e["kind"] == "component"]
    assert components and all(isinstance(e["metadata"].get("pins"), list) for e in components)
    sensor = next(e for e in components if e["metadata"]["family"] == "temperature_sensor")
    assert {p["name"]: p["label"] for p in sensor["metadata"]["pins"]}["signal"] == "DAT"


def test_graph_route_keeps_stored_pin_snapshot():
    from aura.workspace.server import _with_pins
    stored = [{"name": "x", "label": "X", "role": "passive", "voltageRange": None}]
    graph = {"entities": [{"id": "a", "kind": "component", "metadata": {"family": "fan", "pins": stored}},
                          {"id": "b", "kind": "component", "metadata": {"family": "fan"}}, {"id": "c", "kind": "connection", "metadata": {}}]}
    out = _with_pins(graph)
    assert out["entities"][0]["metadata"]["pins"] is stored and [p["name"] for p in out["entities"][1]["metadata"]["pins"]] == ["power", "ground"]
    assert "pins" not in out["entities"][2]["metadata"] and "pins" not in graph["entities"][1]["metadata"]
